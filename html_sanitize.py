"""sanitize کردن HTML آموزش/محتوای اپ که از ادیتور Quill پنل میاد — قبل از این
مستقیم توی innerHTML مینی‌اپ (`openTutorial()` در app.js) بدون هیچ فیلتری تزریق
می‌شد؛ یعنی هر چیزی که در دیتابیس `tutorials.body` ذخیره بشه (چه از خود Quill،
چه از یه درخواست دستکاری‌شده به روت ذخیره — پنل ادمین CSRF token نداره، بخش ۱۳
CLAUDE.md) بدون تغییر به مرورگر همهٔ بازدیدکننده‌ها می‌رسید. این ماژول سمت سرور
و در تک‌نقطهٔ خروجی API (`api.py: api_tutorial_detail`) اعمال می‌شه — یعنی حتی
دادهٔ قدیمی‌تر که قبل از این تغییر ذخیره شده هم محافظت می‌شه، بدون نیاز به مهاجرت.

فقط با کتابخانهٔ استاندارد پایتون (html.parser) — بدون وابستگی تازه.
"""
from html.parser import HTMLParser

_ALLOWED_TAGS = {
    "p", "br", "b", "strong", "i", "em", "u", "s", "strike", "span", "div",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "img",
    "blockquote", "pre", "code", "table", "thead", "tbody", "tr", "td", "th",
    "hr", "sub", "sup",
}
# تگ‌هایی که کلاً خطرناکن — هم خودشون هم محتوای داخلیشون دور ریخته می‌شه
_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "form", "svg", "link", "meta"}

_ALLOWED_ATTRS = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt"},
    "span": {"style"},
    "div": {"style"},
    "p": {"style"},
    "td": {"style", "colspan", "rowspan"},
    "th": {"style", "colspan", "rowspan"},
}
_SAFE_URL_SCHEMES = ("http://", "https://", "mailto:", "tel:", "/", "#")
_SAFE_STYLE_PROPS = ("text-align", "color", "background-color", "font-weight", "font-style", "text-decoration")


def _safe_url(value: str) -> str:
    v = (value or "").strip()
    low = v.lower().replace("\t", "").replace("\n", "").replace(" ", "")
    if low.startswith(("javascript:", "data:", "vbscript:")):
        return ""
    if not v.lower().startswith(_SAFE_URL_SCHEMES):
        # مسیر نسبی بدون / ابتدایی (مثل "img/x.png") هم بی‌خطره؛ فقط اسکیم‌های
        # صریح خطرناک بالا رد می‌شن، بقیه (شامل مسیر نسبی خالی از اسکیم) مجازن
        if ":" in v.split("/")[0]:
            return ""
    return v


def _safe_style(value: str) -> str:
    out = []
    for decl in (value or "").split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if prop not in _SAFE_STYLE_PROPS:
            continue
        low_val = val.lower()
        if "expression" in low_val or "javascript" in low_val or "url(" in low_val or "import" in low_val:
            continue
        out.append(f"{prop}: {val}")
    return "; ".join(out)


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._drop_depth = 0  # تودرتویی تگ‌های _DROP_CONTENT_TAGS

    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=True)

    def _emit_start(self, tag, attrs, self_closing):
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        if tag not in _ALLOWED_TAGS:
            return
        allowed = _ALLOWED_ATTRS.get(tag, set())
        kept = []
        for name, value in attrs:
            name = (name or "").lower()
            if name.startswith("on"):
                continue
            if name not in allowed:
                continue
            if name in ("href", "src"):
                safe = _safe_url(value or "")
                if not safe:
                    continue
                kept.append((name, safe))
            elif name == "style":
                safe = _safe_style(value or "")
                if safe:
                    kept.append((name, safe))
            else:
                kept.append((name, value or ""))
        if tag == "a":
            kept = [kv for kv in kept if kv[0] != "target"] + [("target", "_blank"), ("rel", "noopener noreferrer")]
        attr_str = "".join(f' {k}="{_esc_attr(v)}"' for k, v in kept)
        self.out.append(f"<{tag}{attr_str}{'/' if self_closing else ''}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth:
            return
        if tag in _ALLOWED_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._drop_depth:
            return
        self.out.append(_esc_text(data))

    def handle_entityref(self, name):
        if not self._drop_depth:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self._drop_depth:
            self.out.append(f"&#{name};")


def _esc_text(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def sanitize_html(html_str: str) -> str:
    """ورودی HTML خام (مثلاً از Quill) → خروجی HTML فقط با تگ/attribute های
    لیست‌سفید. هیچ‌وقت استثنا پرتاب نمی‌کنه — ورودی خراب فقط باعث خروجی ناقص/خالی
    می‌شه، نه کرش کل صفحه."""
    if not html_str:
        return ""
    try:
        p = _Sanitizer()
        p.feed(html_str)
        p.close()
        return "".join(p.out)
    except Exception:
        return _esc_text(html_str)
