from django import forms
from django.utils.safestring import mark_safe


class ConditionWidget(forms.Textarea):
    def render(self, name, value, attrs=None, renderer=None):
        textarea = super().render(name, value, attrs, renderer)

        field_id = attrs.get("id", "")

        html = f"""
        <div style="display:flex; gap:26px; align-items:center;">
            <div style="flex:1;">
                {textarea}
            </div>
            <div>
                <button type="button"
                        class="button condition-ui-open"
                        data-target="{field_id}">
                    Help
                </button>
            </div>
        </div>
        """
        return mark_safe(html)
