from django import forms
from django.utils.safestring import mark_safe


class HelpWidget(forms.Textarea):
    def __init__(self, attrs=None, target=""):
        super().__init__(attrs)
        self.target = target
    
    def render(self, name, value, target = None, attrs = None, renderer = None):
        textarea = super().render(name, value, attrs, renderer)

        field_id = attrs.get("id", "")

        html = f"""
        <div style="display:flex; gap:26px; align-items:center;">
            <div style="flex:1;">
                {textarea}
            </div>
            <div>
                <button type="button"
                        class="button {self.target}-ui-open"
                        data-target="{field_id}">
                    Help
                </button>
            </div>
        </div>
        """
        return mark_safe(html)