document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".clickable-row").forEach((row) => {
        row.style.cursor = "pointer";
        row.addEventListener("click", (event) => {
            if (event.target.closest("a, button, input, form")) {
                return;
            }
            const href = row.dataset.href;
            if (href) {
                window.location.href = href;
            }
        });
    });

    const chatBox = document.querySelector(".support-messages");
    if (chatBox) {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});
