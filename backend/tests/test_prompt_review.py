"""图片提示词评审服务单元测试。"""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestReviewPrompts:
    """测试提示词评审逻辑。"""

    def test_review_pass_when_no_api_key(self, mock_db, sample_scenes, sample_raw_text):
        """无 API Key 时直接通过。"""
        with patch("app.services.prompt_review.get_provider_key_sync", return_value=None):
            from app.services.prompt_review import review_prompts
            result = review_prompts(mock_db, 1, sample_scenes, sample_raw_text)
        assert result["overall_pass"] is True
        assert len(result["scenes"]) == 2
        assert all(s["pass"] for s in result["scenes"])

    def test_review_returns_correct_structure(self, mock_db, sample_scenes, sample_raw_text):
        """检查返回结构正确性。"""
        mock_response = {
            "overall_pass": True,
            "scenes": [
                {"scene_id": 1, "pass": True, "score": 85, "notes": "描述准确", "suggested_prompt": ""},
                {"scene_id": 2, "pass": True, "score": 80, "notes": "", "suggested_prompt": ""},
            ],
        }
        with patch("app.services.prompt_review.get_provider_key_sync", return_value="test-key"):
            with patch("app.services.prompt_review.httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": json.dumps(mock_response)}}]
                }
                mock_client.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
                mock_client.return_value.__exit__ = MagicMock(return_value=False)

                from app.services.prompt_review import review_prompts
                result = review_prompts(mock_db, 1, sample_scenes, sample_raw_text)

        assert "overall_pass" in result
        assert "scenes" in result
        assert isinstance(result["scenes"], list)

    def test_review_fail_returns_suggestions(self, mock_db, sample_scenes, sample_raw_text):
        """评审不通过时应返回改进建议。"""
        mock_response = {
            "overall_pass": False,
            "scenes": [
                {"scene_id": 1, "pass": True, "score": 85, "notes": ""},
                {
                    "scene_id": 2, "pass": False, "score": 40,
                    "notes": "提示词中描述与原文不符",
                    "suggested_prompt": "月下窗前，书生仰望明月吟诗",
                },
            ],
        }
        with patch("app.services.prompt_review.get_provider_key_sync", return_value="test-key"):
            with patch("app.services.prompt_review.httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": json.dumps(mock_response)}}]
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
                mock_client.return_value.__exit__ = MagicMock(return_value=False)

                from app.services.prompt_review import review_prompts
                result = review_prompts(mock_db, 1, sample_scenes, sample_raw_text)

        assert result["overall_pass"] is False
        failed = [s for s in result["scenes"] if not s["pass"]]
        assert len(failed) >= 1
        assert "suggested_prompt" in failed[0]

    def test_review_handles_api_error(self, mock_db, sample_scenes, sample_raw_text):
        """API 调用失败时应默认通过。"""
        with patch("app.services.prompt_review.get_provider_key_sync", return_value="test-key"):
            with patch("app.services.prompt_review.httpx.Client") as mock_client:
                mock_client.return_value.__enter__ = MagicMock(
                    return_value=MagicMock(post=MagicMock(side_effect=Exception("timeout")))
                )
                mock_client.return_value.__exit__ = MagicMock(return_value=False)

                from app.services.prompt_review import review_prompts
                result = review_prompts(mock_db, 1, sample_scenes, sample_raw_text)

        assert result["overall_pass"] is True


class TestRegeneratePrompt:
    """测试提示词重新生成。"""

    def test_regen_without_api_key(self, mock_db):
        """无 API Key 时返回原始提示词。"""
        scene = {"visual_prompt": "original prompt", "suggested_prompt": "suggested"}
        with patch("app.services.prompt_review.get_provider_key_sync", return_value=None):
            from app.services.prompt_review import regenerate_prompt
            result = regenerate_prompt(mock_db, scene, "需要更多细节", "小说原文")
        assert result == "original prompt"

    def test_regen_returns_new_prompt(self, mock_db):
        """API 正常时返回新提示词。"""
        scene = {"visual_prompt": "old prompt"}
        with patch("app.services.prompt_review.get_provider_key_sync", return_value="test-key"):
            with patch("app.services.prompt_review.httpx.Client") as mock_client:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": "new improved scene description"}}]
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
                mock_client.return_value.__exit__ = MagicMock(return_value=False)

                from app.services.prompt_review import regenerate_prompt
                result = regenerate_prompt(mock_db, scene, "需要更多细节", "原文")

        assert result == "new improved scene description"
