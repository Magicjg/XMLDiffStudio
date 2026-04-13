# XMLDiffStudio v0.2.0

## Novedades principales

- Reestructura del proyecto en modulos separados
- Motor de diff mejorado para XML y JSON
- Mejor manejo de namespaces, contenido mixto y listas repetidas
- Comparacion en segundo plano para evitar congelar la UI
- Filtros, busqueda y colores por tipo de diferencia
- Vista de detalle lado a lado de `Antes` y `Despues`
- Drag and drop para cargar archivos
- Preferencias persistentes
- Tema claro y oscuro
- Nuevo icono de aplicacion
- Splash screen al iniciar
- Build listo para `.exe`

## Verificacion

- `py_compile`: OK
- `unittest`: OK
- build `.exe`: OK

## Build

```powershell
.\build.ps1
```

Artefacto esperado:

```text
dist/XMLDiffStudio/XMLDiffStudio.exe
```
