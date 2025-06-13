import os
from dotenv import load_dotenv
from crewai.llm import LLM

load_dotenv()

# CREW AI LLM setup
def get_crewai_llm():
    vars = {
        "key": os.getenv("AZURE_OPENAI_API_KEY"),
        "url": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "ver": os.getenv("AZURE_OPENAI_API_VERSION"),
        "name": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    }
    missing = [k for k, v in vars.items() if not v]
    if missing:
        raise ValueError(f"Missing env vars: {', '.join(missing)}")
    return LLM(
        model=f"azure/{vars['name']}",
        api_key=vars["key"],
        base_url=vars["url"],
        api_version=vars["ver"]
    )