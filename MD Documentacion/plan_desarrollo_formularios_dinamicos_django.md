# Plan de desarrollo — MVP de formularios dinámicos en Django

## 1. Objetivo

Construir una primera versión funcional de formularios dinámicos dentro de una app Django llamada `core`, usando SQLite como base de datos por defecto.

El objetivo principal es validar si la arquitectura funciona antes de escalarla a un sistema más completo.

El sistema debe permitir:

- Crear formularios dinámicos.
- Crear campos asociados a un formulario.
- Probar distintos tipos de input.
- Renderizar un formulario dinámico desde base de datos.
- Validar los datos usando `forms.Form` de Django.
- Guardar respuestas en un `JSONField`.
- Visualizar respuestas guardadas.
- Tener una página `home` simple como punto central del CRUD.

---

## 2. Alcance inicial del MVP

Este MVP no busca ser un constructor visual avanzado de formularios.  
La prioridad es probar el flujo completo de backend, validación, guardado y visualización.

Tipos de campo mínimos a soportar:

| Tipo | Uso |
|---|---|
| `text` | Texto corto |
| `textarea` | Texto largo |
| `integer` | Número entero |
| `select` | Selector con opciones |
| `checkbox` | Booleano |
| `email` | Correo electrónico |
| `date` | Fecha |

---

## 3. Stack técnico

- Django.
- App: `core`.
- Base de datos: SQLite por defecto.
- Templates HTML simples.
- Django Forms.
- `JSONField` para guardar respuestas.
- CRUD simple basado en vistas tradicionales de Django.

---

## 4. Estructura esperada del proyecto

```txt
project/
├── manage.py
├── project/
│   ├── settings.py
│   ├── urls.py
│   └── ...
└── core/
    ├── models.py
    ├── forms.py
    ├── views.py
    ├── urls.py
    ├── admin.py
    └── templates/
        └── core/
            ├── home.html
            ├── dynamic_form_create.html
            ├── dynamic_form_edit.html
            ├── dynamic_form_confirm_delete.html
            ├── dynamic_field_create.html
            ├── dynamic_field_edit.html
            ├── dynamic_field_confirm_delete.html
            ├── dynamic_form_fill.html
            ├── dynamic_form_responses.html
            └── dynamic_response_detail.html
```

---

# 5. Configuración base

## 5.1 Registrar la app `core`

En `settings.py`, verificar que `core` esté dentro de `INSTALLED_APPS`.

Pseudo código:

```python
INSTALLED_APPS = [
    ...
    "core",
]
```

---

## 5.2 Configurar rutas principales

En el archivo principal de URLs del proyecto, incluir las URLs de `core`.

Pseudo código:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]
```

---

## 5.3 Crear rutas internas de `core`

Crear `core/urls.py`.

Rutas mínimas necesarias:

```python
urlpatterns = [
    path("", views.home, name="home"),

    path("forms/create/", views.dynamic_form_create, name="dynamic_form_create"),
    path("forms/<int:form_id>/edit/", views.dynamic_form_edit, name="dynamic_form_edit"),
    path("forms/<int:form_id>/delete/", views.dynamic_form_delete, name="dynamic_form_delete"),

    path("forms/<int:form_id>/fields/create/", views.dynamic_field_create, name="dynamic_field_create"),
    path("fields/<int:field_id>/edit/", views.dynamic_field_edit, name="dynamic_field_edit"),
    path("fields/<int:field_id>/delete/", views.dynamic_field_delete, name="dynamic_field_delete"),

    path("forms/<int:form_id>/fill/", views.dynamic_form_fill, name="dynamic_form_fill"),
    path("forms/<int:form_id>/responses/", views.dynamic_form_responses, name="dynamic_form_responses"),
    path("responses/<int:response_id>/", views.dynamic_response_detail, name="dynamic_response_detail"),
]
```

---

# 6. Modelos

## 6.1 Modelo `DynamicForm`

Representa un formulario dinámico creado por el sistema.

Campos recomendados:

```txt
DynamicForm
-----------
id
name
description
is_active
created_at
updated_at
```

Pseudo código:

```python
class DynamicForm(models.Model):
    name = CharField(max_length=150)
    description = TextField(blank=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

Buenas prácticas:

- `name` debe ser obligatorio.
- `description` puede ser opcional.
- `is_active` permite desactivar formularios sin eliminarlos físicamente.
- `created_at` y `updated_at` ayudan a depurar y auditar cambios.
- Evitar borrar formularios si ya tienen respuestas asociadas.

---

## 6.2 Modelo `DynamicField`

Representa un campo dentro de un formulario dinámico.

Campos recomendados:

```txt
DynamicField
------------
id
form
label
field_type
required
order
help_text
placeholder
min_value
max_value
min_length
max_length
is_active
created_at
updated_at
```

Pseudo código:

```python
class DynamicField(models.Model):
    FIELD_TYPES = [
        ("text", "Texto corto"),
        ("textarea", "Texto largo"),
        ("integer", "Número entero"),
        ("select", "Selector"),
        ("checkbox", "Checkbox"),
        ("email", "Email"),
        ("date", "Fecha"),
    ]

    form = ForeignKey(DynamicForm, related_name="fields")
    label = CharField(max_length=150)
    field_type = CharField(max_length=30, choices=FIELD_TYPES)

    required = BooleanField(default=True)
    order = PositiveIntegerField(default=0)

    help_text = CharField(max_length=255, blank=True)
    placeholder = CharField(max_length=150, blank=True)

    min_value = IntegerField(null=True, blank=True)
    max_value = IntegerField(null=True, blank=True)

    min_length = PositiveIntegerField(null=True, blank=True)
    max_length = PositiveIntegerField(null=True, blank=True)

    is_active = BooleanField(default=True)

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

Buenas prácticas:

- Ordenar los campos usando `order`.
- Usar `is_active` para ocultar campos sin romper respuestas antiguas.
- No borrar físicamente campos si ya existen respuestas históricas.
- Los campos tipo `select` deberían tener opciones activas antes de responder el formulario.
- `min_value` y `max_value` aplican principalmente a números.
- `min_length` y `max_length` aplican principalmente a texto.

---

## 6.3 Modelo `DynamicFieldOption`

Representa las opciones de un campo tipo `select`.

Campos recomendados:

```txt
DynamicFieldOption
------------------
id
field
value
label
order
is_active
```

Pseudo código:

```python
class DynamicFieldOption(models.Model):
    field = ForeignKey(DynamicField, related_name="options")
    value = CharField(max_length=100)
    label = CharField(max_length=150)
    order = PositiveIntegerField(default=0)
    is_active = BooleanField(default=True)
```

Ejemplo:

```txt
Campo: Área de trabajo

Opciones:
- backend / Backend
- frontend / Frontend
- unreal / Unreal Engine
```

Buenas prácticas:

- `value` debe ser estable, porque es el dato que se guarda.
- `label` puede cambiar porque es visual.
- Evitar valores duplicados dentro del mismo campo.
- No borrar opciones antiguas si ya fueron usadas en respuestas.

---

## 6.4 Modelo `DynamicFormResponse`

Representa una respuesta enviada por un usuario.

Campos recomendados:

```txt
DynamicFormResponse
-------------------
id
form
data
created_at
```

Pseudo código:

```python
class DynamicFormResponse(models.Model):
    form = ForeignKey(DynamicForm, related_name="responses")
    data = JSONField(default=dict)
    created_at = DateTimeField(auto_now_add=True)
```

Ejemplo de JSON recomendado:

```json
{
    "field_1": {
        "field_id": 1,
        "label": "Nombre completo",
        "type": "text",
        "value": "Matías"
    },
    "field_2": {
        "field_id": 2,
        "label": "Edad",
        "type": "integer",
        "value": 28
    },
    "field_3": {
        "field_id": 3,
        "label": "Área",
        "type": "select",
        "value": "backend"
    }
}
```

Buenas prácticas:

- Guardar metadata del campo junto con el valor.
- Esto permite que las respuestas antiguas sigan siendo legibles aunque después cambie el label del campo.
- No guardar directamente `request.POST`.
- Guardar siempre datos validados desde `cleaned_data`.

---

# 7. Formularios Django para el CRUD

## 7.1 Formulario para crear y editar `DynamicForm`

Crear un `ModelForm`.

Pseudo código:

```python
class DynamicFormModelForm(forms.ModelForm):
    class Meta:
        model = DynamicForm
        fields = [
            "name",
            "description",
            "is_active",
        ]
```

Validaciones recomendadas:

```python
def clean_name(self):
    name = limpiar espacios
    si name está vacío:
        levantar ValidationError
    retornar name
```

---

## 7.2 Formulario para crear y editar `DynamicField`

Crear un `ModelForm`.

Pseudo código:

```python
class DynamicFieldModelForm(forms.ModelForm):
    class Meta:
        model = DynamicField
        fields = [
            "label",
            "field_type",
            "required",
            "order",
            "help_text",
            "placeholder",
            "min_value",
            "max_value",
            "min_length",
            "max_length",
            "is_active",
        ]
```

Validaciones recomendadas:

```python
def clean(self):
    si min_value y max_value existen:
        validar que min_value <= max_value

    si min_length y max_length existen:
        validar que min_length <= max_length

    si field_type == "checkbox":
        required puede ignorarse o mantenerse como referencia visual

    retornar cleaned_data
```

---

## 7.3 Formulario para crear y editar `DynamicFieldOption`

Crear un `ModelForm`.

Pseudo código:

```python
class DynamicFieldOptionModelForm(forms.ModelForm):
    class Meta:
        model = DynamicFieldOption
        fields = [
            "value",
            "label",
            "order",
            "is_active",
        ]
```

Validaciones recomendadas:

```python
def clean_value(self):
    value = limpiar espacios
    si value está vacío:
        levantar ValidationError
    retornar value
```

---

# 8. Formulario dinámico runtime

## 8.1 Objetivo

Crear una clase `DynamicFormBuilder` que construya un `forms.Form` en tiempo de ejecución según los campos guardados en la base de datos.

Esta clase es el centro técnico del sistema.

No representa un modelo fijo.  
Representa un formulario que cambia según la configuración almacenada.

---

## 8.2 Pseudo código general

```python
class DynamicFormBuilder(forms.Form):

    def __init__(self, *args, dynamic_form=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.dynamic_form = dynamic_form

        si dynamic_form no existe:
            return

        fields = dynamic_form.fields.filter(is_active=True).order_by("order", "id")

        para cada field en fields:
            field_name = f"field_{field.id}"

            si field.field_type == "text":
                self.fields[field_name] = CharField(...)

            si field.field_type == "textarea":
                self.fields[field_name] = CharField(widget=Textarea...)

            si field.field_type == "integer":
                self.fields[field_name] = IntegerField(...)

            si field.field_type == "email":
                self.fields[field_name] = EmailField(...)

            si field.field_type == "date":
                self.fields[field_name] = DateField(widget=DateInput...)

            si field.field_type == "checkbox":
                self.fields[field_name] = BooleanField(required=False...)

            si field.field_type == "select":
                cargar opciones activas
                self.fields[field_name] = ChoiceField(...)
```

---

## 8.3 Reglas por tipo de campo

### Text

```python
forms.CharField(
    label=field.label,
    required=field.required,
    min_length=field.min_length,
    max_length=field.max_length,
    help_text=field.help_text,
    widget=forms.TextInput(attrs={
        "placeholder": field.placeholder,
    })
)
```

---

### Textarea

```python
forms.CharField(
    label=field.label,
    required=field.required,
    min_length=field.min_length,
    max_length=field.max_length,
    help_text=field.help_text,
    widget=forms.Textarea(attrs={
        "placeholder": field.placeholder,
        "rows": 4,
    })
)
```

---

### Integer

```python
forms.IntegerField(
    label=field.label,
    required=field.required,
    min_value=field.min_value,
    max_value=field.max_value,
    help_text=field.help_text,
)
```

---

### Email

```python
forms.EmailField(
    label=field.label,
    required=field.required,
    help_text=field.help_text,
)
```

---

### Date

```python
forms.DateField(
    label=field.label,
    required=field.required,
    help_text=field.help_text,
    widget=forms.DateInput(attrs={
        "type": "date",
    })
)
```

---

### Checkbox

Los checkbox deben tratarse con cuidado.

En HTML, cuando un checkbox no está marcado, normalmente no llega en el `POST`.

Por eso, a nivel de Django, conviene configurarlo como:

```python
forms.BooleanField(
    label=field.label,
    required=False,
    help_text=field.help_text,
)
```

Resultado esperado:

```txt
Marcado   -> True
No marcado -> False
```

---

### Select

```python
choices = []

si field.required == False:
    choices.append(("", "Seleccione una opción"))

para cada option activa ordenada:
    choices.append((option.value, option.label))

forms.ChoiceField(
    label=field.label,
    required=field.required,
    choices=choices,
    help_text=field.help_text,
)
```

Validación importante:

- Si el usuario manipula el HTML y envía un valor no existente, `ChoiceField` debe rechazarlo.
- Esto prueba que la validación ocurre en backend y no solo en frontend.

---

# 9. Guardado de respuestas

## 9.1 Objetivo

Convertir `form.cleaned_data` en un JSON descriptivo y persistente.

No guardar solamente:

```json
{
    "field_1": "Matías"
}
```

Guardar mejor:

```json
{
    "field_1": {
        "field_id": 1,
        "label": "Nombre completo",
        "type": "text",
        "value": "Matías"
    }
}
```

---

## 9.2 Helper `build_response_data`

Pseudo código:

```python
def build_response_data(dynamic_form, cleaned_data):
    response_data = {}

    fields = dynamic_form.fields.filter(is_active=True).order_by("order", "id")

    para cada field en fields:
        field_name = f"field_{field.id}"
        value = cleaned_data.get(field_name)

        si value es date:
            value = value.isoformat()

        response_data[field_name] = {
            "field_id": field.id,
            "label": field.label,
            "type": field.field_type,
            "value": value,
        }

    return response_data
```

---

# 10. Vistas

## 10.1 Vista `home`

Objetivo:

Mostrar una página central con la lista de formularios y acciones.

Pseudo código:

```python
def home(request):
    forms = DynamicForm.objects.all().order_by("-created_at")

    render "core/home.html" con:
        forms
```

La página debe mostrar:

```txt
- ID
- Nombre
- Estado
- Fecha de creación
- Acciones
```

Acciones por formulario:

```txt
- Editar
- Desactivar
- Agregar campo
- Responder
- Ver respuestas
```

Buenas prácticas:

- No cargar todas las respuestas en `home`.
- Mostrar solo información resumida.
- Diferenciar formularios inactivos.
- Más adelante se puede agregar contador de campos y respuestas.

---

## 10.2 Crear formulario

Pseudo código:

```python
def dynamic_form_create(request):
    si request.method == "POST":
        form = DynamicFormModelForm(request.POST)

        si form.is_valid():
            form.save()
            redirect("home")

    si request.method == "GET":
        form = DynamicFormModelForm()

    render "core/dynamic_form_create.html" con form
```

---

## 10.3 Editar formulario

Pseudo código:

```python
def dynamic_form_edit(request, form_id):
    dynamic_form = get_object_or_404(DynamicForm, id=form_id)

    si request.method == "POST":
        form = DynamicFormModelForm(request.POST, instance=dynamic_form)

        si form.is_valid():
            form.save()
            redirect("home")

    si request.method == "GET":
        form = DynamicFormModelForm(instance=dynamic_form)

    fields = dynamic_form.fields.all().order_by("order", "id")

    render "core/dynamic_form_edit.html" con:
        form
        dynamic_form
        fields
```

---

## 10.4 Desactivar formulario

Para el MVP, se recomienda desactivar en vez de borrar.

Pseudo código:

```python
def dynamic_form_delete(request, form_id):
    dynamic_form = get_object_or_404(DynamicForm, id=form_id)

    si request.method == "POST":
        dynamic_form.is_active = False
        dynamic_form.save()
        redirect("home")

    render "core/dynamic_form_confirm_delete.html" con dynamic_form
```

Buenas prácticas:

- No eliminar físicamente si ya existen respuestas.
- El nombre de la vista puede ser `delete`, pero internamente puede hacer soft delete.
- Más adelante se puede renombrar a `deactivate`.

---

## 10.5 Crear campo

Pseudo código:

```python
def dynamic_field_create(request, form_id):
    dynamic_form = get_object_or_404(DynamicForm, id=form_id)

    si request.method == "POST":
        form = DynamicFieldModelForm(request.POST)

        si form.is_valid():
            field = form.save(commit=False)
            field.form = dynamic_form
            field.save()

            redirect("dynamic_form_edit", form_id=dynamic_form.id)

    si request.method == "GET":
        form = DynamicFieldModelForm()

    render "core/dynamic_field_create.html" con:
        form
        dynamic_form
```

---

## 10.6 Editar campo

Pseudo código:

```python
def dynamic_field_edit(request, field_id):
    field = get_object_or_404(DynamicField, id=field_id)

    si request.method == "POST":
        form = DynamicFieldModelForm(request.POST, instance=field)

        si form.is_valid():
            form.save()
            redirect("dynamic_form_edit", form_id=field.form.id)

    si request.method == "GET":
        form = DynamicFieldModelForm(instance=field)

    options = field.options.all().order_by("order", "id")

    render "core/dynamic_field_edit.html" con:
        form
        field
        options
```

Nota:

Para el MVP, las opciones de los campos `select` pueden administrarse desde el admin de Django.  
Luego se puede agregar CRUD propio para opciones.

---

## 10.7 Desactivar campo

Pseudo código:

```python
def dynamic_field_delete(request, field_id):
    field = get_object_or_404(DynamicField, id=field_id)

    si request.method == "POST":
        field.is_active = False
        field.save()
        redirect("dynamic_form_edit", form_id=field.form.id)

    render "core/dynamic_field_confirm_delete.html" con field
```

---

## 10.8 Llenar formulario dinámico

Esta es la vista más importante del MVP.

Pseudo código:

```python
def dynamic_form_fill(request, form_id):
    dynamic_form = get_object_or_404(
        DynamicForm.objects.prefetch_related("fields__options"),
        id=form_id,
        is_active=True
    )

    si request.method == "POST":
        form = DynamicFormBuilder(
            request.POST,
            dynamic_form=dynamic_form
        )

        si form.is_valid():
            response_data = build_response_data(
                dynamic_form,
                form.cleaned_data
            )

            DynamicFormResponse.objects.create(
                form=dynamic_form,
                data=response_data
            )

            redirect("dynamic_form_responses", form_id=dynamic_form.id)

    si request.method == "GET":
        form = DynamicFormBuilder(dynamic_form=dynamic_form)

    render "core/dynamic_form_fill.html" con:
        dynamic_form
        form
```

Buenas prácticas:

- Usar `prefetch_related("fields__options")`.
- Reconstruir el formulario tanto en GET como en POST.
- Validar con `form.is_valid()`.
- Guardar solo `form.cleaned_data`, no `request.POST`.
- No permitir responder formularios inactivos.

---

## 10.9 Ver respuestas de un formulario

Pseudo código:

```python
def dynamic_form_responses(request, form_id):
    dynamic_form = get_object_or_404(DynamicForm, id=form_id)

    responses = dynamic_form.responses.all().order_by("-created_at")

    render "core/dynamic_form_responses.html" con:
        dynamic_form
        responses
```

Buenas prácticas:

- En MVP se puede listar todo.
- Más adelante agregar paginación.
- No cargar respuestas gigantes en una tabla principal.

---

## 10.10 Ver detalle de respuesta

Pseudo código:

```python
def dynamic_response_detail(request, response_id):
    response = get_object_or_404(DynamicFormResponse, id=response_id)

    render "core/dynamic_response_detail.html" con:
        response
```

Template esperado:

```txt
Para cada elemento dentro de response.data:
    mostrar label
    mostrar type
    mostrar value
```

---

# 11. Templates mínimos

## 11.1 `home.html`

Debe incluir:

```txt
Título: Formularios dinámicos

Botón:
- Crear formulario

Tabla:
- ID
- Nombre
- Estado
- Fecha creación
- Acciones
```

Acciones:

```txt
Editar
Desactivar
Agregar campo
Responder
Ver respuestas
```

---

## 11.2 `dynamic_form_create.html`

Debe incluir:

```txt
Título: Crear formulario
Formulario renderizado
Botón guardar
Botón volver
```

---

## 11.3 `dynamic_form_edit.html`

Debe incluir:

```txt
Título: Editar formulario
Formulario renderizado
Botón guardar
Botón volver

Sección:
Campos del formulario
```

Tabla de campos:

```txt
- Label
- Tipo
- Requerido
- Orden
- Estado
- Acciones
```

Acciones por campo:

```txt
Editar
Desactivar
```

---

## 11.4 `dynamic_field_create.html`

Debe incluir:

```txt
Título: Agregar campo al formulario
Nombre del formulario padre
Formulario del campo
Botón guardar
Botón volver
```

---

## 11.5 `dynamic_field_edit.html`

Debe incluir:

```txt
Título: Editar campo
Formulario del campo
Botón guardar
Botón volver

Si el campo es select:
    mostrar opciones existentes
```

---

## 11.6 `dynamic_form_fill.html`

Debe incluir:

```txt
Nombre del formulario
Descripción del formulario
Formulario dinámico renderizado por Django
Botón enviar
```

Pseudo template:

```html
<form method="post">
    csrf_token
    form.as_p
    button Enviar
</form>
```

---

## 11.7 `dynamic_form_responses.html`

Debe incluir:

```txt
Título: Respuestas del formulario
Nombre del formulario

Tabla:
- ID respuesta
- Fecha
- Acción ver detalle
```

---

## 11.8 `dynamic_response_detail.html`

Debe mostrar la respuesta en formato legible:

```txt
Nombre completo: Matías
Edad: 28
Área: Backend
Acepta términos: Sí
```

También puede incluir un bloque debug opcional:

```txt
JSON completo de la respuesta
```

---

# 12. Flujo técnico a bajo/medio nivel

## 12.1 Flujo GET para llenar formulario

```txt
1. Usuario entra a /forms/1/fill/.
2. Django recibe la request.
3. La vista busca DynamicForm con id=1.
4. Se cargan sus DynamicField activos.
5. Se cargan sus DynamicFieldOption si existen.
6. Se crea DynamicFormBuilder.
7. DynamicFormBuilder recorre cada DynamicField.
8. Por cada campo, crea un Field real de Django.
9. El formulario queda almacenado temporalmente en self.fields.
10. Django renderiza el HTML.
11. El navegador muestra el formulario.
```

---

## 12.2 Flujo POST para guardar formulario

```txt
1. Usuario completa el formulario.
2. El navegador envía un POST.
3. Django recibe request.POST.
4. La vista vuelve a buscar el mismo DynamicForm.
5. La vista vuelve a construir DynamicFormBuilder con la misma estructura.
6. Django compara request.POST contra self.fields.
7. Cada Field ejecuta su validación.
8. Si hay errores, se vuelve a renderizar el formulario con mensajes de error.
9. Si todo es válido, Django genera cleaned_data.
10. cleaned_data se transforma en response_data.
11. response_data se guarda en DynamicFormResponse.data.
12. El usuario es redirigido a respuestas o home.
```

---

## 12.3 Punto clave

El formulario debe reconstruirse en el backend tanto en GET como en POST.

No basta con que el input exista en HTML.

Ejemplo:

```html
<input name="field_1">
```

Ese input puede llegar en `request.POST`, pero si no existe en `form.fields`, Django no lo validará como parte del formulario.

Por eso el backend debe construir:

```python
self.fields["field_1"] = forms.CharField(...)
```

Eso le dice a Django:

```txt
Espero recibir field_1.
Debe ser texto.
Es requerido.
Tiene estas reglas.
Debe aparecer en cleaned_data solo si es válido.
```

---

# 13. Casos de prueba manuales

## 13.1 Crear formulario

Datos:

```txt
Nombre: Evaluación inicial
Descripción: Formulario de prueba para validar campos dinámicos.
Activo: Sí
```

Resultado esperado:

```txt
El formulario aparece en home.
```

---

## 13.2 Campo tipo text

Datos:

```txt
Label: Nombre completo
Tipo: text
Requerido: Sí
Min length: 3
Max length: 100
Placeholder: Ingrese su nombre
Orden: 1
```

Pruebas:

```txt
Enviar vacío -> debe fallar.
Enviar "Ma" -> debe fallar.
Enviar "Matías Inayao" -> debe pasar.
```

---

## 13.3 Campo tipo integer

Datos:

```txt
Label: Edad
Tipo: integer
Requerido: Sí
Min value: 18
Max value: 99
Orden: 2
```

Pruebas:

```txt
Enviar texto -> debe fallar.
Enviar 15 -> debe fallar.
Enviar 28 -> debe pasar.
Enviar 120 -> debe fallar.
```

---

## 13.4 Campo tipo select

Datos:

```txt
Label: Área
Tipo: select
Requerido: Sí
Orden: 3
```

Opciones:

```txt
backend / Backend
frontend / Frontend
unreal / Unreal Engine
```

Pruebas:

```txt
Enviar sin seleccionar -> debe fallar si es requerido.
Enviar backend -> debe pasar.
Manipular POST con valor inexistente -> debe fallar.
```

---

## 13.5 Campo tipo checkbox

Datos:

```txt
Label: Acepta términos
Tipo: checkbox
Requerido: No
Orden: 4
```

Pruebas:

```txt
Sin marcar -> debe guardar False.
Marcado -> debe guardar True.
```

---

## 13.6 Campo tipo email

Datos:

```txt
Label: Correo
Tipo: email
Requerido: Sí
Orden: 5
```

Pruebas:

```txt
Enviar "hola" -> debe fallar.
Enviar "test@test.com" -> debe pasar.
```

---

## 13.7 Campo tipo date

Datos:

```txt
Label: Fecha de ingreso
Tipo: date
Requerido: No
Orden: 6
```

Pruebas:

```txt
Enviar vacío -> debe pasar si no es requerido.
Enviar fecha válida -> debe guardar string tipo YYYY-MM-DD.
```

---

## 13.8 Ver respuesta guardada

Después de enviar una respuesta válida:

Resultado esperado:

```txt
Debe existir una fila en DynamicFormResponse.
Debe tener form_id correcto.
Debe tener data JSON con field_id, label, type y value.
Debe poder verse desde response_detail.
```

---

# 14. Pruebas de robustez

## 14.1 Campo desactivado

Flujo:

```txt
1. Crear un campo.
2. Enviar una respuesta.
3. Desactivar el campo.
4. Volver a llenar el formulario.
```

Resultado esperado:

```txt
El campo desactivado ya no aparece.
Las respuestas antiguas siguen conservando su label y value dentro del JSON.
```

---

## 14.2 Formulario desactivado

Flujo:

```txt
1. Desactivar formulario.
2. Intentar entrar a /forms/id/fill/.
```

Resultado esperado:

```txt
No debería permitir responder.
Puede devolver 404 o una página controlada indicando que el formulario no está activo.
```

---

## 14.3 Select sin opciones

Flujo:

```txt
1. Crear campo tipo select.
2. No crear opciones.
3. Intentar llenar formulario.
```

Resultado esperado:

```txt
El sistema debería mostrar el select vacío o un error de configuración.
```

Mejora futura:

```txt
Evitar activar un formulario si contiene selects obligatorios sin opciones.
```

---

## 14.4 Manipulación del POST

Flujo:

```txt
1. Crear select con opciones backend/frontend.
2. Manipular manualmente el POST.
3. Enviar field_3 = "valor_inexistente".
```

Resultado esperado:

```txt
ChoiceField debe rechazar el valor.
```

Esto confirma que la validación real está en backend.

---

# 15. Buenas prácticas

## 15.1 Backend

- Validar siempre usando Forms de Django.
- No guardar directamente `request.POST`.
- Usar `form.cleaned_data`.
- Usar `get_object_or_404`.
- Usar `prefetch_related("fields__options")` al llenar formularios.
- No permitir responder formularios inactivos.
- No borrar físicamente formularios/campos si ya tienen respuestas.
- Guardar metadata del campo dentro del JSON de respuesta.

---

## 15.2 Base de datos

- SQLite es suficiente para el MVP.
- No optimizar antes de validar el flujo.
- Si el sistema crece, evaluar PostgreSQL.
- Evitar usar JSON como reemplazo total de modelos normales.
- Usar JSON solo para respuestas dinámicas o datos variables.

---

## 15.3 Templates

- Mantener HTML simple.
- Usar `csrf_token`.
- Mostrar errores de validación.
- No ocultar errores del formulario.
- Agregar botones claros para volver.
- No depender únicamente de validaciones frontend.

---

## 15.4 Seguridad básica

- No confiar en inputs del navegador.
- No guardar valores que no pasaron por `form.is_valid()`.
- No permitir crear campos asociados a formularios inexistentes.
- Más adelante agregar login y permisos.
- Más adelante separar permisos de administración y respuesta.

---

# 16. Orden recomendado de desarrollo

## Fase 1 — Base mínima

```txt
1. Verificar app core.
2. Crear modelos.
3. Crear migraciones.
4. Ejecutar migrate.
5. Registrar modelos en admin.
6. Crear home simple.
```

Comandos:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## Fase 2 — CRUD de formularios

```txt
1. Crear DynamicFormModelForm.
2. Crear vista create.
3. Crear vista edit.
4. Crear vista delete/deactivate.
5. Mostrar formularios en home.
```

---

## Fase 3 — CRUD de campos

```txt
1. Crear DynamicFieldModelForm.
2. Crear vista para agregar campo.
3. Crear vista para editar campo.
4. Crear vista para desactivar campo.
5. Mostrar campos dentro de edición del formulario.
```

---

## Fase 4 — Opciones de select

```txt
1. Crear modelo DynamicFieldOption.
2. Registrar en admin.
3. Crear opciones desde admin para la primera prueba.
4. Más adelante crear CRUD visual de opciones.
```

---

## Fase 5 — Builder dinámico

```txt
1. Crear DynamicFormBuilder.
2. Soportar text.
3. Soportar integer.
4. Soportar select.
5. Soportar checkbox.
6. Soportar textarea.
7. Soportar email.
8. Soportar date.
```

---

## Fase 6 — Guardar respuestas

```txt
1. Crear build_response_data.
2. Crear vista dynamic_form_fill.
3. Validar POST.
4. Guardar DynamicFormResponse.
5. Redirigir a respuestas o home.
```

---

## Fase 7 — Visualizar respuestas

```txt
1. Crear vista de respuestas por formulario.
2. Crear vista detalle de respuesta.
3. Mostrar label, type y value.
4. Agregar bloque debug opcional con JSON completo.
```

---

# 17. Resultado esperado del MVP

Al terminar el MVP, el flujo completo debería ser:

```txt
1. Entrar a home.
2. Crear formulario "Evaluación inicial".
3. Agregar campo "Nombre completo" tipo text.
4. Agregar campo "Edad" tipo integer.
5. Agregar campo "Área" tipo select.
6. Crear opciones para el select.
7. Agregar campo "Acepta términos" tipo checkbox.
8. Entrar a "Responder formulario".
9. Completar los datos.
10. Enviar.
11. Ver la respuesta guardada.
12. Entrar al detalle de respuesta.
13. Confirmar que el JSON tenga field_id, label, type y value.
```

---

# 18. Criterios de aceptación

El MVP se considera funcional si cumple:

```txt
- Se pueden crear formularios.
- Se pueden editar formularios.
- Se pueden desactivar formularios.
- Se pueden crear campos.
- Se pueden editar campos.
- Se pueden desactivar campos.
- Los campos aparecen ordenados.
- El formulario dinámico se renderiza correctamente.
- Django valida campos requeridos.
- Django valida integer.
- Django valida email.
- Django valida opciones permitidas.
- Checkbox guarda True o False.
- Date se guarda correctamente en JSON.
- Las respuestas quedan guardadas en DynamicFormResponse.
- Las respuestas pueden verse desde la interfaz.
```

---

# 19. Mejoras futuras fuera del MVP

No implementar todavía:

```txt
- Login y permisos.
- Constructor visual de formularios.
- Drag and drop para ordenar campos.
- CRUD visual para opciones de select.
- Exportar respuestas a CSV.
- Exportar respuestas a Excel.
- Paginación de respuestas.
- Validaciones condicionales.
- Campos dependientes.
- Formularios por secciones.
- Clonado de formularios.
- Versionado de formularios.
- Auditoría de cambios.
- Soft delete completo.
- Migración a PostgreSQL.
```

---

# 20. Nota de diseño importante

Este sistema debe entenderse como un motor de captura dinámica de datos, no como reemplazo total de los modelos normales de Django.

Regla práctica:

```txt
Datos importantes para negocio:
usar modelos normales con columnas reales.

Datos variables, secundarios o configurables:
usar formulario dinámico + JSONField.
```

Ejemplo:

```txt
Producto, stock, factura, cliente, usuario:
modelo normal.

Checklist, encuesta, inspección, observación extra:
formulario dinámico.
```

Para este MVP, el enfoque correcto es probar el motor dinámico con SQLite, validar el flujo y luego decidir si conviene evolucionarlo a una arquitectura más robusta.
