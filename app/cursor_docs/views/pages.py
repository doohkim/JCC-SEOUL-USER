from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView

from cursor_docs.services.catalog import (
    CATEGORY_PERMISSIONS,
    CATEGORY_POLICY,
    CATEGORY_TEMPLATE,
    CATEGORY_DETAIL_URL_NAMES,
    CATEGORY_LIST_URL_NAMES,
    get_doc,
    list_docs,
)
from cursor_docs.services.markdown import extract_section_toc, render_markdown
from users.mixins import SuperuserRequiredMixin


class CursorDocsAccessMixin(LoginRequiredMixin, SuperuserRequiredMixin):
    login_url = reverse_lazy("user_login")


_VALID_CATEGORIES = {CATEGORY_POLICY, CATEGORY_TEMPLATE, CATEGORY_PERMISSIONS}

_CATEGORY_HEADINGS = {
    CATEGORY_POLICY: "Cursor 정책",
    CATEGORY_TEMPLATE: "Cursor 템플릿",
    CATEGORY_PERMISSIONS: "사용자 권한",
}


class CursorDocListView(CursorDocsAccessMixin, ListView):
    template_name = "cursor_docs/list.html"
    context_object_name = "docs"
    paginate_by = 30

    def get_category(self) -> str:
        tab = (self.kwargs.get("category") or CATEGORY_POLICY).strip().lower()
        if tab not in _VALID_CATEGORIES:
            return CATEGORY_POLICY
        return tab

    def get_queryset(self):
        return list_docs(self.get_category())

    def get(self, request, *args, **kwargs):
        category = self.get_category()
        if category == CATEGORY_PERMISSIONS:
            docs = list_docs(category)
            if len(docs) == 1:
                return redirect(
                    reverse(
                        CATEGORY_DETAIL_URL_NAMES[category],
                        kwargs={"slug": docs[0].slug},
                    )
                )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = self.get_category()
        ctx["cursor_docs_tab"] = category
        ctx["page_heading"] = _CATEGORY_HEADINGS[category]
        ctx["detail_url_name"] = CATEGORY_DETAIL_URL_NAMES[category]
        return ctx


class CursorDocDetailView(CursorDocsAccessMixin, DetailView):
    template_name = "cursor_docs/detail.html"
    context_object_name = "doc"
    slug_url_kwarg = "slug"

    def get_category(self) -> str:
        tab = (self.kwargs.get("category") or CATEGORY_POLICY).strip().lower()
        if tab not in _VALID_CATEGORIES:
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
        ctx["list_url_name"] = CATEGORY_LIST_URL_NAMES[category]
        if category == CATEGORY_PERMISSIONS:
            ctx["permissions_toc"] = extract_section_toc(self._raw_content)
        return ctx
