import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def empty_cache(device: str) -> None:
    if device == "cuda":
        torch.cuda.empty_cache()
    elif device == "mps":
        torch.mps.empty_cache()


class Model:
    def __init__(self, checkpoint: str, device: str = None, dtype=None):
        self.device = device or pick_device()
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint)

        if dtype is None:
            if self.device == "cpu":
                dtype = torch.bfloat16
            else:
                dtype = "auto"

        if dtype == "auto":
            self.model = AutoModelForCausalLM.from_pretrained(checkpoint).to(self.device)
        else:
            self.model = AutoModelForCausalLM.from_pretrained(checkpoint, torch_dtype=dtype).to(self.device)

        self.model.eval()

        self.vllm_engine = None
        if self.device in ["cuda", "mps"]:
            try:
                from vllm import LLM
                vllm_dtype = "bfloat16" if dtype == "auto" or dtype == torch.bfloat16 else "float16"
                self.vllm_engine = LLM(
                    model=checkpoint,
                    dtype=vllm_dtype,
                    trust_remote_code=True,
                    enforce_eager=True if self.device == "mps" else False,
                    device=self.device,
                    gpu_memory_utilization=0.9
                )
            except ImportError:
                pass

    def batch_generate_sample(
            self,
            prompts: list[str],
            n=128,
            temperature=1.0,
    ) -> list[str]:

        rendered = [self._render(p) for p in prompts]

        if self.vllm_engine is not None:
            from vllm import SamplingParams

            params = SamplingParams(
                temperature=temperature,
                top_p=1.0,
                max_tokens=n,
            )

            outputs = self.vllm_engine.generate(
                rendered,
                params,
            )

            return [
                out.outputs[0].text
                for out in outputs
            ]

        inputs = self.tokenizer(
            rendered,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=n,
                do_sample=True,
                temperature=temperature,
            )

        responses = []

        for i in range(len(prompts)):
            generated = out[i][inputs.input_ids.shape[1]:]
            responses.append(
                self.tokenizer.decode(
                    generated,
                    skip_special_tokens=True,
                )
            )

        return responses
    def _render(self, prompt: str) -> str:
        return self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def get_logits(self, prompt: str):
        text = self._render(prompt)
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.device)
        with torch.no_grad():
            output = self.model(**model_inputs)
        return output.logits[0, -1, :]

    def get_hidden_states(self, prompt: str) -> torch.Tensor:
        text = self._render(prompt)
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.device)
        with torch.no_grad():
            output = self.model(**model_inputs, output_hidden_states=True)
        last = torch.stack([h[0, -1, :] for h in output.hidden_states])
        return last.float().cpu()

    def score_continuation(self, prompt: str, continuation: str) -> float:
        prompt_ids = self.tokenizer(self._render(prompt), add_special_tokens=False).input_ids
        cont_ids = self.tokenizer(continuation, add_special_tokens=False).input_ids
        input_ids = torch.tensor([prompt_ids + cont_ids], device=self.device)
        with torch.no_grad():
            logits = self.model(input_ids=input_ids).logits.float()
        len_p, len_c = len(prompt_ids), len(cont_ids)
        pred = logits[len_p - 1: len_p + len_c - 1]
        logprobs = torch.log_softmax(pred, dim=-1)
        target = torch.tensor(cont_ids, device=self.device)
        token_lp = logprobs[torch.arange(len_c), target]
        return token_lp.mean().item()

    def best_continuation(self, prompt: str, variants) -> float:
        return max(self.score_continuation(prompt, v) for v in variants)

    def generate_start(self, prompt, n=256):
        return self.batch_generate_start([prompt], n=n)[0]

    def batch_generate_start(self, prompts: list[str], n=256) -> list[str]:
        rendered_prompts = [self._render(p) for p in prompts]

        if self.vllm_engine is not None:
            from vllm import SamplingParams

            sampling_params = SamplingParams(
                temperature=0.0,
                top_p=1.0,
                max_tokens=n,
            )

            outputs = self.vllm_engine.generate(
                rendered_prompts,
                sampling_params,
            )

            return [
                out.outputs[0].text
                for out in outputs
            ]

        results = []
        for text in rendered_prompts:
            inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
            with torch.no_grad():
                out = self.model.generate(**inputs, max_new_tokens=n, do_sample=False)
            results.append(self.tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True))
        return results

    def generate_sample(self, prompt, n=128, temperature=1.0):

        if self.vllm_engine is not None:
            from vllm import SamplingParams

            sampling_params = SamplingParams(
                temperature=temperature,
                top_p=1.0,
                max_tokens=n,
            )

            outputs = self.vllm_engine.generate(
                [self._render(prompt)],
                sampling_params,
            )

            return outputs[0].outputs[0].text

        text = self._render(prompt)

        inputs = self.tokenizer(
            text,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=n,
                do_sample=True,
                temperature=temperature,
            )

        return self.tokenizer.decode(
            out[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True,
        )