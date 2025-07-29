from evalscope.run import run_task
from evalscope.utils.logger import get_logger

logger = get_logger()

eval_task_cfg = {
    "eval_backend": "RAGEval",
    "eval_config": {
        "tool": "RAGAS",
        "eval": {
            "testset_file": "rag.json",
            "critic_llm": {
                "model_name": "qwen2.5-7b-int4",
                "api_base": "http://172.29.230.70:8501/v1",
                "api_key": "xx"
            },
            "embeddings": {
                "model_name": "text-embedding-3-small",
                "api_base": "https://geekai.dev/api/v1",
                "api_key": "sk-VdcrbcBT0M03jm8ADkPBT7kt2vNbNv0DBarcYNjDGZY4voZI",
                "dimensions": 1024
            },
            "metrics": [
                "Faithfulness",
                "AnswerRelevancy",
                "ContextPrecision",
                "AnswerCorrectness",
                "ContextRecall"
            ],
            "language": "chinese"
        },
    },
}

# Run task
k = run_task(task_cfg=eval_task_cfg)
print(k)