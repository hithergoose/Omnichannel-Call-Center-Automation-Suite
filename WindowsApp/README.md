# Omnichannel Call Center Engine & Automation Suite

## 🚀 Descripción General
Solución integral de escritorio diseñada para optimizar la productividad de equipos de cobranza y ventas. El sistema integra gestión de bases de datos masivas, automatización de telefonía (dialer), grabación de llamadas en tiempo real y protocolos de seguridad de grado empresarial.

**Impacto:** Capacidad de gestión de +45,000 registros con latencia mínima y automatización de flujos de trabajo que anteriormente requerían múltiples herramientas externas.

## 🛠️ Stack Tecnológico
*   **Lenguaje:** Python 3.x
*   **Frontend:** PyWebView + DataTables (HTML5/JS/CSS) para renderizado de alto rendimiento.
*   **Base de Datos & Auth:** Supabase (PostgreSQL) & SQLite para persistencia offline.
*   **Automatización & Scraping:** Playwright (Headless browser para gestión de tokens).
*   **Multimedia:** Windows API (WASAPI/MME) para captura y mezcla de audio.
*   **Redes:** Protocolos ARP/UDP para autodescubrimiento de dispositivos móviles.

## ✨ Funcionalidades Clave (Ingeniería)

### 1. Seguridad y Control de Sesión (Hardening)
*   **Heartbeat Monitor:** Implementación de una ventana de latido de 45s para prevenir la duplicidad de sesiones.
*   **Remote Kill-Switch:** Sistema de escucha en tiempo real para bloqueo o expulsión inmediata de usuarios desde un panel administrativo.
*   **Cierre por Inactividad:** Monitor de eventos de periféricos (mouse/teclado) para protección de datos sensibles.

### 2. Motor de Visualización Ultrarrápido
*   **Renderizado Diferido:** Capacidad para procesar +45k registros mediante paginación inteligente y filtros avanzados con operadores matemáticos (RegEx y lógica comparativa en tiempo real).
*   **Extractor de Leads Inteligente:** Algoritmo basado en Expresiones Regulares (RegEx) para limpieza y normalización de números telefónicos internacionales.

### 3. Conectividad y Telefonía Híbrida
*   **Auto-Discovery de Dispositivos:** Protocolos de rastreo en tarjetas de red físicas (ARP/IP) y Handshake UDP para vinculación automática entre PC y dispositivo Android sin configuración manual.
*   **Dual-Channel Recording:** Captura de audio bidireccional (Loopback + Micrófono) mezclado en tiempo real a formato MP3 mediante la API nativa de Windows.

### 4. Resiliencia de Datos
*   **Offline First:** Sistema de colas encriptadas en SQLite que garantiza la integridad de las gestiones en caso de fallos de red, con reintentos automáticos (Worker background).
*   **Token Hijacking Legal:** Automatización de login mediante Playwright para la sincronización transparente de credenciales con el sistema central (SISCO).

## 🧠 Desafíos Técnicos y Soluciones
*   **Desafío:** La latencia al cargar 45,000 clientes bloqueaba la interfaz de usuario.
*   **Solución:** Implementé una arquitectura de renderizado diferido y paginación en el lado del cliente, reduciendo el tiempo de carga de 2 minutos a menos de 1 segundo.
*   **Desafío:** La captura de audio en Windows suele requerir drivers virtuales complejos.
*   **Solución:** Desarrollé un módulo usando `ctypes` para interactuar directamente con WASAPI, logrando grabaciones de alta calidad sin necesidad de software de terceros.