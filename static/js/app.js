const menuButton = document.getElementById("menuButton");
const sidebar = document.getElementById("sidebar");

if (menuButton && sidebar) {
  menuButton.addEventListener("click", () => sidebar.classList.toggle("open"));
}

document.querySelectorAll(".nav-item").forEach((link) => {
  if (window.location.pathname === link.pathname) {
    link.classList.add("active");
  }
});

function getCookie(name) {
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))
    ?.split("=")
    .slice(1)
    .join("=");
}

function updateAlertCounters(count) {
  document.querySelectorAll(".alert-count, .nav-alert-count").forEach((badge) => {
    badge.textContent = count;
    badge.classList.toggle("is-hidden", count === 0);
  });
  const label = document.getElementById("alertUnreadLabel");
  if (label) label.textContent = `${count} non lue${count > 1 ? "s" : ""}`;
}

function showGpsAlert(alert) {
  let stack = document.getElementById("liveAlertStack");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "liveAlertStack";
    stack.className = "live-alert-stack";
    document.body.appendChild(stack);
  }
  const notification = document.createElement("a");
  notification.href = "/alertes/";
  notification.className = "live-alert-notification";
  notification.innerHTML = `
    <span class="live-alert-icon">!</span>
    <span><strong>${alert.type}</strong><small>${alert.message}</small></span>
  `;
  stack.appendChild(notification);
  setTimeout(() => notification.remove(), 12000);
}

async function checkDisconnectedGps() {
  const url = document.body.dataset.gpsAlertCheckUrl;
  if (!url || document.hidden) return;
  try {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": decodeURIComponent(getCookie("csrftoken") || ""),
        Accept: "application/json",
      },
    });
    if (!response.ok) return;
    const result = await response.json();
    updateAlertCounters(result.unread_count);
    result.created.forEach(showGpsAlert);
  } catch (error) {
    // La prochaine vérification réessaiera automatiquement.
  }
}

if (document.body.dataset.gpsAlertCheckUrl) {
  checkDisconnectedGps();
  setInterval(checkDisconnectedGps, 30000);
}

const contractType = document.getElementById("id_type_contrat");
const contractStart = document.getElementById("id_date_debut_contrat");
const contractEnd = document.getElementById("id_date_fin_contrat");

function updateContractFields() {
  if (!contractType || !contractEnd) return;
  const endField = contractEnd.closest(".field");
  const isCdd = contractType.value === "CDD";
  if (endField) endField.classList.toggle("contract-field-hidden", !isCdd);
  contractEnd.required = isCdd;
  if (contractStart) contractStart.required = isCdd;
  if (!isCdd) contractEnd.value = "";
}

if (contractType) {
  contractType.addEventListener("change", updateContractFields);
  updateContractFields();
}
