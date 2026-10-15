// Adds a Copy button inside every input marked data-copy. The Clipboard API exists only over HTTPS or on localhost
if (navigator.clipboard) {
  document.querySelectorAll("input[data-copy]").forEach((input) => {
    const wrapper = document.createElement("span");
    wrapper.className = "copy-field";
    input.replaceWith(wrapper);
    wrapper.append(input);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    if (input.labels.length) {
      button.setAttribute("aria-label", `Copy ${input.labels[0].textContent.replace(/:$/, "")}`);
    }

    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(input.value);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Copy failed";
      }
      setTimeout(() => {
        button.textContent = "Copy";
      }, 1500);
    });

    wrapper.append(button);
  });
}
