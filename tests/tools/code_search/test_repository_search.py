"""Functional tests for Repository Search Tool."""

import json

import pytest

import akd_ext.tools.code_search.repository_search as repository_search_module
from akd_ext.tools.code_search.repository_search import (
    RepositorySearchTool,
    RepositorySearchToolConfig,
    RepositorySearchToolInputSchema,
    RepositorySearchToolOutputSchema,
)


class TestRepositorySearchBackend:
    """Guards the SDE backend contract: current code endpoint + min_score on every request."""

    @pytest.mark.unit
    def test_default_targets_current_code_endpoint(self):
        config = RepositorySearchToolConfig()
        assert config.base_url == "https://dyejsbdumgpqz.cloudfront.net/api/code/search"
        assert config.min_score == 0.0

    @pytest.mark.unit
    def test_sde_search_sends_min_score(self, monkeypatch):
        """min_score must be on every payload: the endpoint applies a 0.55 default and returns
        nothing when it is omitted, so a dropped min_score silently breaks the tool."""
        captured: dict = {}

        class _Response:
            @staticmethod
            def json() -> dict:
                return {"documents": []}

        def _post(url, headers=None, data=None):
            captured["url"] = url
            captured["payload"] = json.loads(data)
            return _Response()

        monkeypatch.setattr(repository_search_module.requests, "post", _post)

        RepositorySearchTool(config=RepositorySearchToolConfig())._sde_search(page=1, query="anything")

        assert captured["url"].endswith("/api/code/search")
        assert captured["payload"]["min_score"] == 0.0


class TestRepositorySearchTool:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query",
        [
            "nasa python",
            "pds software",
        ],
    )
    async def test_repository_search_tool(self, query: str):
        """Test Repository Search Tool functionality.

        Args:
            query: Code search query to test
        """
        config = RepositorySearchToolConfig(page_size=2)
        tool = RepositorySearchTool(config=config)
        result = await tool.arun(RepositorySearchToolInputSchema(queries=[query]))

        assert isinstance(result, RepositorySearchToolOutputSchema)
        assert len(result.results) > 0

        # Verify each result has repository metadata and reliability score
        for item in result.results:
            assert hasattr(item, "repository_metadata")
            assert hasattr(item, "reliability_score")
            assert item.repository_metadata.stars >= 0
            assert item.repository_metadata.forks >= 0

    @pytest.mark.parametrize(
        "page_size,result_size",
        [
            (3, 3),
            (8, 8),
            (10, 10),
            (11, 10),  # Capped at max 10
            (55, 10),  # Capped at max 10
            (100, 10),  # Capped at max 10
        ],
    )
    @pytest.mark.asyncio
    async def test_repository_search_tool_results_number(self, page_size: int, result_size: int):
        """Test Repository Search Tool results number."""
        config = RepositorySearchToolConfig(page_size=page_size)
        tool = RepositorySearchTool(config=config)
        # "nasa python" has >100 results in the SDE code index so any page_size up to the 10 cap works
        result = await tool.arun(RepositorySearchToolInputSchema(queries=["nasa python"]))
        assert len(result.results) == result_size
