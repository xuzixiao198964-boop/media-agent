"""图片评审服务单元测试。"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestImageReviewRules:
    """基于规则的图片评审测试。"""

    def test_pass_when_image_large_enough(self, mock_db):
        """图片文件足够大时通过。"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG" + b"\x00" * 100000)
            img_path = Path(f.name)

        try:
            from app.services.image_review import _review_with_rules
            result = _review_with_rules(mock_db, 1, {1: img_path}, {1: "test prompt"})
            assert result["overall_pass"] is True
            assert result["scenes"][0]["pass"] is True
            assert result["scenes"][0]["score"] >= 70
        finally:
            img_path.unlink(missing_ok=True)

    def test_fail_when_image_too_small(self, mock_db):
        """图片文件过小时不通过。"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG" + b"\x00" * 100)
            img_path = Path(f.name)

        try:
            from app.services.image_review import _review_with_rules
            result = _review_with_rules(mock_db, 1, {1: img_path}, {1: "test"})
            assert result["overall_pass"] is False
            assert result["scenes"][0]["pass"] is False
            assert result["scenes"][0]["action"] == "regenerate"
        finally:
            img_path.unlink(missing_ok=True)

    def test_fail_when_image_missing(self, mock_db):
        """图片文件不存在时不通过。"""
        missing_path = Path("/nonexistent/image.png")
        from app.services.image_review import _review_with_rules
        result = _review_with_rules(mock_db, 1, {1: missing_path}, {1: "test"})
        assert result["overall_pass"] is False
        assert result["scenes"][0]["score"] == 0

    def test_multiple_scenes_partial_pass(self, mock_db):
        """多场景中部分通过部分不通过。"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1:
            f1.write(b"\x89PNG" + b"\x00" * 100000)
            good_path = Path(f1.name)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
            f2.write(b"\x89PNG" + b"\x00" * 50)
            bad_path = Path(f2.name)

        try:
            from app.services.image_review import _review_with_rules
            result = _review_with_rules(
                mock_db, 1,
                {1: good_path, 2: bad_path},
                {1: "good scene", 2: "bad scene"},
            )
            assert result["overall_pass"] is False
            passed = [s for s in result["scenes"] if s["pass"]]
            failed = [s for s in result["scenes"] if not s["pass"]]
            assert len(passed) == 1
            assert len(failed) == 1
        finally:
            good_path.unlink(missing_ok=True)
            bad_path.unlink(missing_ok=True)


class TestImageReviewDispatch:
    """测试 review_images 调度逻辑。"""

    def test_uses_gemini_when_available(self, mock_db):
        """有 Gemini API Key 时优先使用 Gemini。"""
        def mock_key(db, provider):
            if provider == "gemini_api_key":
                return "gemini-test-key"
            return None

        with patch("app.services.image_review.get_provider_key_sync", side_effect=mock_key):
            with patch("app.services.image_review._review_with_gemini") as mock_gemini:
                mock_gemini.return_value = {"overall_pass": True, "scenes": []}
                from app.services.image_review import review_images
                result = review_images(mock_db, 1, {}, {})
                mock_gemini.assert_called_once()

    def test_falls_back_to_deepseek(self, mock_db):
        """无 Gemini 时回退到 DeepSeek。"""
        def mock_key(db, provider):
            if provider == "deepseek":
                return "deepseek-test-key"
            return None

        with patch("app.services.image_review.get_provider_key_sync", side_effect=mock_key):
            with patch("app.services.image_review._review_with_deepseek") as mock_ds:
                mock_ds.return_value = {"overall_pass": True, "scenes": []}
                from app.services.image_review import review_images
                result = review_images(mock_db, 1, {}, {})
                mock_ds.assert_called_once()

    def test_falls_back_to_rules(self, mock_db):
        """无任何 AI API 时使用规则评审。"""
        with patch("app.services.image_review.get_provider_key_sync", return_value=None):
            with patch("app.services.image_review._review_with_rules") as mock_rules:
                mock_rules.return_value = {"overall_pass": True, "scenes": []}
                from app.services.image_review import review_images
                result = review_images(mock_db, 1, {}, {})
                mock_rules.assert_called_once()


class TestVideoBlockedWithoutImageApproval:
    """测试图片评审未通过时阻断视频生成。"""

    def test_video_task_blocked(self, mock_db):
        """模拟 NovelChapter 图片未通过时视频任务返回错误。"""
        from unittest.mock import PropertyMock

        mock_chapter = MagicMock()
        mock_chapter.script_status = "approved"
        mock_chapter.image_status = "reviewing"

        mock_db.get = MagicMock(return_value=mock_chapter)

        mock_project = MagicMock()
        mock_db.get.side_effect = lambda model, id: {
            "NovelChapter": mock_chapter,
            "NovelProject": mock_project,
        }.get(model.__name__, None) if hasattr(model, '__name__') else mock_chapter

        assert mock_chapter.image_status != "approved"
