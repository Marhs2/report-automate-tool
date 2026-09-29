/** `http://` 사설 주소에는 `navigator.clipboard`가 없다. */
export async function copyText(text, host = globalThis) {
    const value = String(text ?? "");
    const clipboard = host.navigator?.clipboard;
    if (typeof clipboard?.writeText === "function") {
        try {
            await clipboard.writeText(value);
            return true;
        } catch {
            /* 권한 거절이나 비보안 출처면 아래 선택 복사로 넘어간다. */
        }
    }
    const doc = host.document;
    if (!doc?.body || typeof doc.execCommand !== "function") return false;
    const area = doc.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "0";
    area.style.left = "0";
    area.style.opacity = "0";
    doc.body.appendChild(area);
    area.focus();
    area.select();
    area.setSelectionRange?.(0, value.length);
    let ok = false;
    try {
        ok = doc.execCommand("copy");
    } catch {
        ok = false;
    }
    area.remove();
    return Boolean(ok);
}
