# ims/src/config/mixins/form_mixin.py
from django import forms

class BootstrapFormMixin:
    """
    Robust Bootstrap mixin for Django forms.

    - Adds sensible Bootstrap classes to widgets (form-control / form-select / form-check-input)
    - Ensures widget.attrs exists and always has a 'class' key (possibly empty)
    - Avoids accessing deprecated attributes (like RadioSelect.renderer)
    - Does not attempt to introspect subwidget objects (which may be dicts)
    - Provides a simple as_p renderer that works with standard BoundField rendering
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            widget = field.widget

            # Ensure widget.attrs exists and has a 'class' key
            if not hasattr(widget, 'attrs') or widget.attrs is None:
                widget.attrs = {}
            # Guarantee 'class' key exists to avoid template lookups failing
            widget.attrs['class'] = widget.attrs.get('class', '')

            # Add appropriate classes depending on widget type
            # Add Bootstrap classes based on widget type
            if isinstance(widget, forms.CheckboxInput):
                # Simple checkbox
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-check-input'

            elif isinstance(widget, forms.RadioSelect):
                # Apply class to the whole group, not subwidgets
                widget.attrs['class'] = widget.attrs.get('class', '') + ' d-block my-1'

            else:
                # All normal inputs
                widget.attrs['class'] = widget.attrs.get('class', '') + ' form-control'

            # Special handling for select dropdowns (exclude RadioSelect)
            if isinstance(widget, forms.Select) and not isinstance(widget, forms.RadioSelect):
                widget.attrs['class'] += ' form-select'


            # If there are any field-level errors, mark widget invalid
            # (we cannot access bound errors here; errors are checked in as_p)
            # We still keep the hook: if later as_p sees errors for this field it will add 'is-invalid'

    def as_p(self):
        """
        Render the form fields as <p> elements with Bootstrap-friendly markup.
        Uses bound fields (self[field_name]) so Django's BoundField rendering is kept.
        """
        output = []

        # Non-field errors at top
        if self.non_field_errors():
            output.append(f"""
            <div class="alert alert-danger" role="alert">
                {' '.join(self.non_field_errors())}
            </div>
            """)

        for field_name, field in self.fields.items():
            bound_field = self[field_name]
            field_errors = bound_field.errors
            error_html = ''
            if field_errors:
                # mark input as invalid by adding 'is-invalid' to widget attrs if possible
                try:
                    # ensure widget attrs has 'class'
                    bound_field.field.widget.attrs['class'] = bound_field.field.widget.attrs.get('class', '') + ' is-invalid'
                except Exception:
                    pass
                error_html = f'<p class="text-danger" style="margin-top: -15px;">{" ".join(field_errors)}</p>'

            help_text_html = ''
            if bound_field.help_text:
                help_text_html = f'<small class="form-text text-muted">{bound_field.help_text}</small>'

            # If CheckboxInput
            if isinstance(bound_field.field.widget, forms.CheckboxInput):
                output.append(f"""
                <div class="form-check mb-3">
                    {bound_field}
                    <label class="form-check-label" for="{bound_field.id_for_label}">
                        {bound_field.label}
                    </label>
                    {error_html}
                    {help_text_html}
                </div>
                """)
            # If RadioSelect, let Django render the group (it will use widget.attrs for input attrs)
            elif isinstance(bound_field.field.widget, forms.RadioSelect):
                # Put the whole radio group inside a wrapper
                output.append(f"""
                <div class="mb-3">
                    <label class="form-label">{bound_field.label}</label>
                    <div class="d-block">
                        {bound_field}
                    </div>
                    {error_html}
                    {help_text_html}
                </div>
                """)
            else:
                # Default rendering (label + field)
                label_html = ''
                if bound_field.label:
                    label_html = f'<label for="{bound_field.id_for_label}" class="mb-1 ps-1">{bound_field.label}</label>'

                output.append(f"""
                <p class="form-group">
                    {label_html}
                    {bound_field}
                    {error_html}
                    {help_text_html}
                </p>
                """)

        return ''.join(output)
