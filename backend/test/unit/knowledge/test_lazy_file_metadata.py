import pytest

from test.unit.support.knowledge import FakeKnowledgeBase


@pytest.mark.asyncio
async def test_base_export_is_explicitly_unsupported(tmp_path):
    kb = FakeKnowledgeBase(str(tmp_path))

    with pytest.raises(NotImplementedError, match="不支持数据导出"):
        await kb.export_data("db", format="csv")
