"""CSS compartilhado entre as páginas para manter a identidade visual do app."""
import streamlit as st

BASE_CSS = """
<style>
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: .03em;
    text-transform: uppercase;
    color: var(--dot-color, #8b949e);
    white-space: nowrap;
}
.badge::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--dot-color, #8b949e);
    display: inline-block;
}
.waba-tag {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    color: #58a6ff;
    background: rgba(88,166,255,0.12);
    padding: 2px 8px;
    border-radius: 6px;
}
.mudanca-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 8px 4px;
    border-bottom: 1px solid #21262d;
}
.mudanca-row:last-child { border-bottom: none; }
.mudanca-numero {
    font-weight: 600;
    color: #e6edf3;
    min-width: 160px;
}
.mudanca-tipo {
    color: #8b949e;
    font-size: 0.8rem;
    min-width: 90px;
}
.mudanca-arrow { color: #8b949e; }
</style>
"""


def inject_base_styles():
    st.markdown(BASE_CSS, unsafe_allow_html=True)
