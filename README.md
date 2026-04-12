# XMLDiffStudio

Aplicacion de escritorio para comparar archivos `XML` o `JSON` y detectar diferencias de estructura, valores, texto y atributos.

## Funciones

- Compara `XML` contra `XML`
- Compara `JSON` contra `JSON`
- Detecta cambios, nodos agregados, eliminados y cambios de tipo
- Preserva mejor `namespaces`, contenido mixto y alineacion de listas repetidas
- Filtra resultados por tipo y texto
- Muestra detalle lado a lado de la diferencia seleccionada
- Copia una diferencia al portapapeles
- Exporta reportes a `TXT`, `CSV` y `JSON`
- Recuerda rutas recientes, filtros y tamano de ventana
- Ejecuta la comparacion en segundo plano para evitar congelar la UI
- Permite arrastrar y soltar archivos sobre `Archivo A` y `Archivo B`
- Incluye preferencias persistentes y empaquetado listo para `.exe`

## Uso

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\XMLDiffStudio.py
```

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Build EXE

```powershell
.\build.ps1
```

El ejecutable se genera en `.\dist\XMLDiffStudio\XMLDiffStudio.exe`.

## Assets

- Icono principal: `assets/xmldiffstudio-icon.ico`
- Vista previa: `assets/xmldiffstudio-icon.png`
