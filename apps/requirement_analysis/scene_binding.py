"""
场景绑定模块：按场景名称解析 AI 模型配置。

当前版本（源码包未附带场景绑定表/字段）统一回退到 role='writer' 的激活配置，
与既有业务逻辑一致（性能测试 AI 分析、对照报告 AI 分析均复用 writer 配置）。
若后续引入场景绑定关系，请在 resolve_scene_config 中优先查询绑定配置后再回退。
"""

import logging

logger = logging.getLogger(__name__)

# 未绑定场景时的默认回退角色
_DEFAULT_ROLE = 'writer'


def resolve_scene_config(scene):
    """
    按场景名解析 AI 模型配置，返回激活的 AIModelConfig 实例；无可用配置时返回 None。

    :param scene: 场景标识，如 'perf_ai'（预留：后续可据此查询场景绑定）
    :return: AIModelConfig 实例或 None
    """
    from apps.requirement_analysis.models import AIModelConfig

    # ---- 场景绑定扩展点 ----
    # 若后续新增场景绑定表（如 SceneBinding），在此优先解析：
    #   bound = SceneBinding.objects.filter(scene=scene, is_active=True).first()
    #   if bound:
    #       cfg = AIModelConfig.objects.filter(id=bound.config_id, is_active=True).first()
    #       if cfg:
    #           return cfg
    # ------------------------

    role = _DEFAULT_ROLE
    cfg = AIModelConfig.objects.filter(role=role, is_active=True).first()
    if cfg is None:
        logger.warning("未找到激活的 AI 模型配置（role=%s），scene=%s", role, scene)
    else:
        logger.info("场景 %s 解析到 AI 模型配置：%s（role=%s）", scene, cfg.model_name, role)
    return cfg
