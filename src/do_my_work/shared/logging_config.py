import logging
from do_my_work.infrastructure.llm_client import AbstractLlmClient

def configure_logging(trace_llm: bool=False) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    AbstractLlmClient.trace=trace_llm