"""数据模型单元测试。"""
import pytest


class TestNovelChapterModel:
    """测试 NovelChapter 模型新字段。"""

    def test_chapter_has_prompt_fields(self):
        """验证 NovelChapter 包含图片提示词评审字段。"""
        from app.models import NovelChapter
        mapper = NovelChapter.__table__
        col_names = {c.name for c in mapper.columns}

        assert "prompt_status" in col_names
        assert "prompt_review_notes" in col_names
        assert "prompt_review_round" in col_names
        assert "image_prompts" in col_names

    def test_chapter_has_image_review_fields(self):
        """验证 NovelChapter 包含图片评审字段。"""
        from app.models import NovelChapter
        mapper = NovelChapter.__table__
        col_names = {c.name for c in mapper.columns}

        assert "image_status" in col_names
        assert "image_review_notes" in col_names
        assert "image_review_round" in col_names

    def test_chapter_prompt_status_default(self):
        """验证 prompt_status 默认值为 pending。"""
        from app.models import NovelChapter
        col = NovelChapter.__table__.c.prompt_status
        assert col.default.arg == "pending"

    def test_chapter_image_status_default(self):
        """验证 image_status 默认值为 pending。"""
        from app.models import NovelChapter
        col = NovelChapter.__table__.c.image_status
        assert col.default.arg == "pending"


class TestChapterReviewModel:
    """测试 ChapterReview 模型扩展字段。"""

    def test_review_has_reviewer_type(self):
        """验证 ChapterReview 包含 reviewer_type 字段。"""
        from app.models import ChapterReview
        col_names = {c.name for c in ChapterReview.__table__.columns}
        assert "reviewer_type" in col_names

    def test_review_has_review_detail(self):
        """验证 ChapterReview 包含 review_detail JSON 字段。"""
        from app.models import ChapterReview
        col_names = {c.name for c in ChapterReview.__table__.columns}
        assert "review_detail" in col_names

    def test_reviewer_type_default(self):
        """验证 reviewer_type 默认值为 human。"""
        from app.models import ChapterReview
        col = ChapterReview.__table__.c.reviewer_type
        assert col.default.arg == "human"
