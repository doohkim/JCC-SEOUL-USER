from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView

from cursor_docs.services.catalog import (
    CATEGORY_POLICY,
    CATEGORY_TEMPLATE,
    get_doc,
    list_docs,
)
from cursor_docs.services.markdown import render_markdown
from users.mixins import SuperuserRequiredMixin


class CursorDocsAccessMixin(LoginRequiredMixin, SuperuserRequiredMixin):
    login_url = reverse_lazy("user_login")


class CursorDocListView(CursorDocsAccessMixin, ListView):
    template_name = "cursor_docs/list.html"
    context_object_name = "docs"
    paginate_by = 30

    def get_category(self) -> str:
        tab = (self.kwargs.get("category") or CATEGORY_POLICY).strip().lower()
        if tab not in {CATEGORY_POLICY, CATEGORY_TEMPLATE}:
            return CATEGORY_POLICY
        return tab

    def get_queryset(self):
        return list_docs(self.get_category())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = self.get_category()
        ctx["cursor_docs_tab"] = category
        ctx["page_heading"] = (
            "Cursor 정책" if category == CATEGORY_POLICY else "Cursor 템플릿"
        )
        return ctx


class CursorDocDetailView(CursorDocsAccessMixin, DetailView):
    template_name = "cursor_docs/detail.html"
    context_object_name = "doc"
    slug_url_kwarg = "slug"

    def get_category(self) -> str:
        tab = (self.kwargs.get("category") or CATEGORY_POLICY).strip().lower()
        if tab not in {CATEGORY_POLICY, CATEGORY_TEMPLATE}:
            raise Http404
        return tab

    def get_object(self, queryset=None):
        result = get_doc(self.get_category(), self.kwargs["slug"])
        if result is None:
            raise Http404
        entry, raw = result
        self._raw_content = raw
        return entry

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = self.get_category()
        ctx["cursor_docs_tab"] = category
        ctx["rendered_body"] = render_markdown(self._raw_content)
        ctx["list_url_name"] = (
            "cursor_docs_policy_list"
            if category == CATEGORY_POLICY
            else "cursor_docs_template_list"
        )
        return ctx
