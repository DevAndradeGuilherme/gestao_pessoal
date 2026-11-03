"""Adaptadores de serviços externos (Google Calendar, Evolution API, OpenAI).

Cada integração expõe um `Protocol` consumido pelos serviços de domínio e uma
implementação real separada, permitindo fakes em testes. Nenhuma integração existe ainda.
"""
