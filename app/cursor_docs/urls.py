from django.urls import path

from cursor_docs.views import CursorDocDetailView, CursorDocListView

urlpatterns = [
    path(
        "cursor-docs/",
        CursorDocListView.as_view(),
        {"category": "policy"},
        name="cursor_docs_home",
    ),
    path(
        "cursor-docs/policy/",
        CursorDocListView.as_view(),
        {"category": "policy"},
        name="cursor_docs_policy_list",
    ),
    path(
        "cursor-docs/template/",
        CursorDocListView.as_view(),
        {"category": "template"},
        name="cursor_docs_template_list",
    ),
    path(
        "cursor-docs/policy/<slug:slug>/",
        CursorDocDetailView.as_view(),
        {"category": "policy"},
        name="cursor_docs_policy_detail",
    ),
    path(
        "cursor-docs/template/<slug:slug>/",
        CursorDocDetailView.as_view(),
        {"category": "template"},
        name="cursor_docs_template_detail",
    ),
]
