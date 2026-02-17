(function () {
  "use strict";

  function ensureModal() {
    if (document.getElementById("condition-ui-modal")) return;

    const modal = document.createElement("div");
    modal.id = "condition-ui-modal";
    modal.innerHTML = `
      <div class="cui-backdrop"></div>
      <div class="cui-panel" role="dialog" aria-modal="true">
        <div class="cui-header">
          <strong>Condition Instructions</strong>
          <button type="button" class="cui-close" aria-label="Close">✕</button>
        </div>

        <div class="cui-body">
          <p><b>What to put into “condition”</b></p>
          <p>Paste a JSON object describing the condition node.</p>

          <p><b>Fields</b></p>
          <ul>
            <li><code>type</code>: <code>"leaf"</code> | <code>"and"</code> | <code>"or"</code></li>
            <li><code>operator</code>: <code>gt</code>, <code>gte</code>, <code>lt</code>, <code>lte</code>, <code>eq</code>, <code>ne</code></li>
            <li><code>threshold</code>: number</li>
            <li><code>occurrences</code>: integer (≥ 1) (OPTIONAL)</li>
            <li><code>window</code>: integer seconds (≥ 1) (OPTIONAL)</li>
          </ul>

          <p><b>Minimal example (leaf)</b></p>
          <pre class="cui-code">{
  "type": "leaf",
  "operator": "gt",
  "threshold": 25.5,
  "occurrences": 3,
  "window_seconds": 60
}</pre>

                  <p><b>Minimal example (and/or)</b></p>
          <pre class="cui-code">
{
    "type": "or",
    "conditions": [
    {
        "type": "leaf",
        "operator": "lt",
        "threshold": 80
    },
    {
        "type": "leaf",
        "operator": "gt",
        "threshold": 60.5,
        "occurrences": 5,
        "window_seconds": 60
    }
]
}
</pre>

          <p><b>Minimal example (Nested And/Ors)</b></p>
          <pre class="cui-code">{
    "type": "or",
    "conditions": [
        {"type": "leaf", "operator": "gt", "threshold": 5.0},
        {"type": "and",
        "conditions": [
            {"type": "leaf", "operator": "gt", "threshold": 15.0},
            {"type": "leaf", "operator": "lt", "threshold": 20.0}
            ]
        },
    ],
}</pre>
</div>
        <div class="cui-footer">
          <button type="button" class="button cui-ok">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const close = () => modal.classList.remove("open");
    modal.querySelector(".cui-backdrop").addEventListener("click", close);
    modal.querySelector(".cui-close").addEventListener("click", close);
    modal.querySelector(".cui-ok").addEventListener("click", close);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal.classList.contains("open")) close();
    });
  }

  function ensureModalAction() {
    if (document.getElementById("action-ui-modal")) return;

    const modal = document.createElement("div");
    modal.id = "action-ui-modal";
    modal.innerHTML = `
      <div class="cui-backdrop"></div>
      <div class="cui-panel" role="dialog" aria-modal="true">
        <div class="cui-header">
          <strong>Action Config Instructions</strong>
          <button type="button" class="cui-close" aria-label="Close">✕</button>
        </div>

        <div class="cui-body">
          <p><b>What to put into “action_config”</b></p>
          <p>Paste a JSON object describing the action_config node.</p>
          <p>Must be a list, can contain multiple notifications and/or stop_machine actions.</p>

          <p><b>Fields</b></p>
          <ul>
            <li><code>type</code>: <code>"notification"</code> | <code>"stop_machine"</code></li>
            <li><code>template_id (notification)</code>: <code>id of templace (int)</code>
            <li><code>machine_id(stop_machine)</code>: string (TEMP-SN1-001)</li>
          </ul>

          <p><b>Example containing one notification and one stop machine</b></p>
          <pre class="cui-code">
[
  {"type": "notification", "template_id": 5}, 
  {"type": "stop_machine", "machine_id": "TEMP-SN1-001"}
]
    </pre>
    </div>
        <div class="cui-footer">
          <button type="button" class="button cui-ok">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const close = () => modal.classList.remove("open");
    modal.querySelector(".cui-backdrop").addEventListener("click", close);
    modal.querySelector(".cui-close").addEventListener("click", close);
    modal.querySelector(".cui-ok").addEventListener("click", close);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal.classList.contains("open")) close();
    });
  }

  function openModal(modal) {
    if (modal === "condition-ui-modal") {
      ensureModal();
    } else {
      ensureModalAction();
    }
    document.getElementById(modal).classList.add("open");
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".condition-ui-open");
    if (!btn) return;
    openModal('condition-ui-modal');
  });
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".action-ui-open");
    if (!btn) return;
    openModal('action-ui-modal');
  });
})();
