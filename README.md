# proyecto-final-programacion-sig
Proyecto Final Curso Programación en SIG GF-0657

# Distribución espacial y análisis de la actividad agrícola en Costa Rica

## Autor

**Luis Vega González**  
Bachiller en Geografía, Universidad de Costa Rica (UCR).

## Descripción del proyecto

Esta aplicación web interactiva tiene como propósito visualizar y explorar información relacionada con la distribución espacial de la actividad agropecuaria y las características de la producción agrícola en Costa Rica.

El proyecto integra dos componentes de análisis complementarios:

### 1. Distribución espacial de la actividad agropecuaria

Se analiza la distribución de la extensión agropecuaria a escala cantonal, mediante indicadores como la superficie agropecuaria, el porcentaje de superficie cantonal destinado a estas actividades y la cantidad de fincas registradas. Se incorporan representaciones cartográficas interactivas para visualizar los patrones espaciales mediante mapas coropléticos y mapas de calor.

### 2. Análisis estadístico de la producción agrícola

Se examinan las principales actividades agrícolas del país a partir de variables como la extensión sembrada, el volumen de producción en toneladas métricas y el rendimiento. Asimismo, se presenta la evolución histórica de la producción de café.

Ambos componentes se desarrollan de manera independiente, dado que utilizan unidades de análisis y variables diferentes. Su integración permite ofrecer una perspectiva complementaria sobre las características de la actividad agrícola nacional.

La aplicación permite explorar la información mediante filtros interactivos, indicadores estadísticos, tablas, gráficos y mapas web.

## Fuentes de información

Los datos utilizados proceden de las siguientes fuentes:

- **VI Censo Nacional Agropecuario (2014):** información agropecuaria a escala cantonal, utilizada para el análisis de la distribución espacial de la actividad agropecuaria.
- **MAG/SEPSA:** información estadística sobre extensión sembrada y producción de las principales actividades agrícolas en Costa Rica.
- **Cartografía cantonal de Costa Rica:** utilizada como referencia geográfica para la representación espacial de los datos.

### Repositorios de los trabajos originales

- [Tarea 2: Análisis estadístico y gráficos de cultivos](https://github.com/luisgonzaveg-prog/tarea2_graficos)
- [Tarea 3: Análisis espacial del Censo Nacional Agropecuario](https://github.com/luisgonzaveg-prog/tarea3)

## Aplicación web

La aplicación fue desarrollada utilizando Python y Streamlit.

**Enlace de acceso:** [Aplicación interactiva en Streamlit Community Cloud](ENLACE_DE_LA_APLICACION)

## Tecnologías y bibliotecas utilizadas

- Python
- Streamlit
- Pandas
- NumPy
- GeoPandas
- Plotly
- Folium
- Streamlit-Folium
- OpenPyXL

Las dependencias y versiones de las bibliotecas se encuentran especificadas en el archivo `requirements.txt`.

## Declaración de uso de inteligencia artificial

Para el desarrollo de este proyecto se utilizó **ChatGPT (OpenAI)** como herramienta de asistencia técnica. Su utilización comprendió consultas sobre procedimientos de programación y desarrollo de aplicaciones web con Streamlit, generación y adaptación de código Python, asesoría para la instalación y configuración de paquetes y bibliotecas faltantes, así como apoyo en la identificación y depuración de errores durante la ejecución de la aplicación.

El código generado y adaptado mediante esta asistencia fue incorporado al proyecto y posteriormente ejecutado, probado y verificado por el autor en el entorno local de desarrollo.

La inteligencia artificial se utilizó como herramienta de apoyo, mientras que las decisiones sobre el contenido, los datos, el enfoque metodológico y la revisión de los resultados correspondieron al autor.

---

**Proyecto final | Curso de Programación en Sistemas de Información Geográfica (SIG)**  
Universidad de Costa Rica (UCR) | 2026
