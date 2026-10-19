"""The model-provider layer: the Anthropic and Gemini clients, the
``complete``/``chat_llm`` entry points every AI feature calls, embeddings,
pricing and the cross-process status store. It knows nothing about
matters, conversations or the case file; those live in ``apps.ai``.
"""
