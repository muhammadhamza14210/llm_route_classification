from openai import AzureOpenAI
from config.settings import settings

client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)

deployments = {
    "small":  settings.AZURE_DEPLOYMENT_SMALL,
    "medium": settings.AZURE_DEPLOYMENT_MEDIUM,
    "large":  settings.AZURE_DEPLOYMENT_LARGE,
}

print("\nTesting Azure Foundry connections...\n")

for tier, deployment in deployments.items():
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "say hi"}],
        )
        reply = response.choices[0].message.content.strip()
        print(f"  ✅ {tier} ({deployment}) → {reply}")
    except Exception as e:
        print(f"  ❌ {tier} ({deployment}) → {e}")