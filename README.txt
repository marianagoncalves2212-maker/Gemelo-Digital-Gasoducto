GEMELO DIGITAL - GASODUCTO TRANS-ANDINO


DESCRIPCIÓN:

Este software permite simular el comportamiento termodinámico, hidráulico y financiero de un gasoducto de 400 km de longitud. Evalúa la viabilidad operativa mediante modelos de flujo de Weymouth y la integridad estructural según la Ecuación de Barlow, permitiendo optimizar el número de estaciones de compresión y la selección de materiales (API 5L).


ESTRUCTURA DEL PROYECTO:

01 Motor de cálculo y control

Contiene el núcleo algorítmico y la arquitectura de la interfaz.

   - dashboard.py (Interfaz principal de Streamlit)

   - requirements.txt (Librerías y dependencias de Python)

   - .streamlit/ (Configuración de entorno visual)

02 Documentación y reportes

Carpeta que integra el sustento técnico y la validación visual
del comportamiento del sistema bajo condiciones críticas.

   - Enunciado_Proyecto_Gasoducto.pdf (Bases del diseño)

   - Evidencia_Estatus_Seguro.png

   - Evidencia_Estatus_Alerta_Termica.png

   - Evidencia_Estatus_Falla_Mecanica.png


INSTRUCCIONES DE DESPLIEGUE:

   - Asegúrese de tener instalado Python 3.9+ en su sistema.

   - Instale las librerías necesarias ejecutando 'pip install -r requirements.txt'.

   - Inicie el simulador desde la raíz del proyecto con el comando:
'python -m streamlit run dashboard.py'


FECHA: Abril 2026