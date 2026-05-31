"""Focused tests for Project Director Skill binding config copy."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.project_director_skill_binding_config import (
    ProjectDirectorSkillBindingConfig,
    SkillBindingConfigStatus,
)
from app.services.project_director_skill_binding_config_service import (
    ProjectDirectorSkillBindingConfigService,
)


def _config(status: SkillBindingConfigStatus) -> ProjectDirectorSkillBindingConfig:
    return ProjectDirectorSkillBindingConfig(
        project_id=uuid4(),
        plan_version_id=uuid4(),
        source_draft_id="pdv:test:1",
        status=status,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (None, "普通项目暂无 AI 主管 Skill 绑定配置。"),
        (
            _config(SkillBindingConfigStatus.PENDING_CONFIRMATION),
            "请在项目详情页确认或拒绝 AI 主管 Skill 绑定建议；确认后仍不会启用 Skill 或启动 Worker。",
        ),
        (
            _config(SkillBindingConfigStatus.CONFIRMED),
            "Skill 绑定建议已确认；这只是项目级配置，不代表已创建真实 Skill 绑定。",
        ),
        (
            _config(SkillBindingConfigStatus.REJECTED),
            "Skill 绑定建议已拒绝；历史配置保留为只读回溯。",
        ),
    ],
)
def test_next_action_uses_chinese_copy_without_question_mark_garbage(
    config: ProjectDirectorSkillBindingConfig | None,
    expected: str,
):
    next_action = ProjectDirectorSkillBindingConfigService._next_action_for(config)

    assert next_action == expected
    assert "?" * 3 not in next_action
    assert "?" * 4 not in next_action
    assert "?" not in next_action
