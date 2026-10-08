/* The eye button beside a password field: shows the password while it is
   pressed, hides it again on the next press. Works for every
   .password-toggle on the page; the input is its previous sibling. */
document.addEventListener("click", function (event) {
  const button = event.target.closest(".password-toggle");
  if (!button) return;
  const input = button.previousElementSibling;
  if (!input || input.tagName !== "INPUT") return;
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  button.setAttribute("aria-pressed", String(show));
  button.setAttribute("aria-label", show ? "Hide password" : "Show password");
  button.querySelector("i").className = show ? "icon-eye-off" : "icon-eye";
  input.focus({ preventScroll: true });
});
