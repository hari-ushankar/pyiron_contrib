import ipywidgets as widgets


class MultiComboBox:
    def __init__(self, **kwargs):
        self.description = kwargs.pop('description', "")
        self.add_unknown = kwargs.pop("add_unknown", False)
        self.value = kwargs.pop('value', [])
        self.options = kwargs.pop("options", None)
        self.disabled = kwargs.pop("disabled", False)
        self.placeholder = kwargs.pop("placeholder", "")
        self.style = kwargs.pop("style", {})
        width = kwargs.pop("width", "212px")
        self.description_width = self.style.pop("description_width", "76px")
        self._outerbox = widgets.HBox(width=width, **kwargs)
        self._kwargs = kwargs

    def widget(self):
        self._update_widget(self._outerbox)
        return self._outerbox

    def _on_click(self, b):
        self.value.remove(b.description)
        self._update_widget(self._outerbox)

    def _on_value_change(self, change):
        if change['new'] not in self.value:
            if change["new"] in self.options or self.add_unknown:
                self.value.append(change['new'])
        self._update_widget(self._outerbox)

    def _update_widget(self, outerbox):
        innerbox = widgets.VBox()
        childs = []
        Combobox = widgets.Combobox(
            description="",
            options=self.options,
            value="",
            placeholder=self.placeholder,
            disabled=self.disabled
        )
        Combobox.continuous_update = False
        Combobox.observe(self._on_value_change, names="value")
        childs.append(Combobox)
        for val in self.value:
            button = widgets.Button(
                description=val,
                tooltip="delete",
                disabled=self.disabled
            )
            button.on_click(self._on_click)
            childs.append(button)
        Label = widgets.Label(
            self.description,
            layout=widgets.Layout(
                display="flex",
                justify_content="flex-end",
                width=self.description_width,
                margin="6px")
        )
        innerbox.children = tuple(childs)

        outerbox.children = tuple([Label, innerbox])
        outerbox.value = self.value
        outerbox.description = self.description


class MultiTextBox:
    def __init__(self, **kwargs):
        self.description = kwargs.pop('description', "")
        self.value = kwargs.pop('value', [])
        self.options = kwargs.pop("options", None)
        self.placeholder = kwargs.pop("placeholder", "")
        self.disabled = kwargs.pop("disabled", False)
        self.style = kwargs.pop("style", {})
        width = kwargs.pop("width", "212px")
        self.description_width = self.style.pop("description_width", "76px")
        self._outerbox = widgets.HBox(width=width, **kwargs)
        self._kwargs = kwargs

    def widget(self):
        self._update_widget(self._outerbox)
        return self._outerbox

    def _on_click(self, b):
        self.value.remove(b.description)
        self._update_widget(self._outerbox)

    def _on_value_change(self, change):
        if change['new'] not in self.value:
            self.value.append(change['new'])
        self._update_widget(self._outerbox)

    def _update_widget(self, outerbox):
        innerbox = widgets.VBox()
        childs = []
        Textbox = widgets.Text(
            description="",
            value="",
            placeholder=self.placeholder,
            disabled=self.disabled,
        )
        Textbox.continuous_update = False
        Textbox.observe(self._on_value_change, names="value")
        childs.append(Textbox)
        for val in self.value:
            button = widgets.Button(
                description=val,
                tooltip="delete",
                disabled=self.disabled
            )
            button.on_click(self._on_click)
            childs.append(button)
        Label = widgets.Label(
            self.description,
            layout=widgets.Layout(
                display="flex",
                justify_content="flex-end",
                width=self.description_width,
                margin="6px")
        )
        innerbox.children = tuple(childs)

        outerbox.children = tuple([Label, innerbox])
        outerbox.value = self.value
        outerbox.description = self.description
