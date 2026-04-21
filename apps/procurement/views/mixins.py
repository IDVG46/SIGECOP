class HtmxTemplateMixin:
    """Devuelve `partial_template_name` cuando la petición viene de HTMX."""

    partial_template_name: str = ""

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return [self.partial_template_name]
        return super().get_template_names()
