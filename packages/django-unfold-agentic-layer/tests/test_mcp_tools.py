import asyncio

from django_unfold_agentic_layer.mcp_server.tools import mcp


def test_all_docs_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert len(tools) == 25
    assert "unfold_get_started" in names
    assert "unfold_search_docs" in names
    assert "unfold_complete_example" in names
