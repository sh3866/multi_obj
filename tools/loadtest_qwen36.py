import time
def main():
    t0=time.time()
    from vllm import LLM, SamplingParams
    llm = LLM(model="Qwen/Qwen3.6-35B-A3B", max_model_len=8192,
              gpu_memory_utilization=0.90, limit_mm_per_prompt={"image":1},
              enforce_eager=True, trust_remote_code=True)
    print(f"[loaded in {time.time()-t0:.0f}s]", flush=True)
    out = llm.generate(["Write a single HTML button with a blue background. Reply with only the HTML."],
                       SamplingParams(max_tokens=80, temperature=0.7))
    print("GEN_OK >>>", out[0].outputs[0].text[:300], flush=True)
if __name__ == "__main__":
    main()
