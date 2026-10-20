These unmodified upstream license texts fill omissions in installed Python wheels
and the Tcl runtime. Third-party copyright names are retained as required.

- `flatbuffers-LICENSE.txt`: https://raw.githubusercontent.com/google/flatbuffers/v25.12.19/LICENSE
- `proxy_tools-LICENSE.txt`: https://raw.githubusercontent.com/jtushman/proxy_tools/master/LICENSE.txt
- `Tcl-LICENSE.txt`: https://raw.githubusercontent.com/tcltk/tcl/core-8-6-16/license.terms
- `WebView2-LICENSE.txt` and `WebView2-NOTICE.txt`: Microsoft.Web.WebView2
  1.0.3856.49 NuGet package, matching the pywebview-bundled SDK DLL version:
  https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.3856.49/microsoft.web.webview2.1.0.3856.49.nupkg
- `OpenSSL-LICENSE.txt` and `OpenSSL-ATTRIBUTION.txt`: bundled Python runtime uses
  OpenSSL 3.5.8, https://github.com/openssl/openssl/tree/openssl-3.5.8
- `Expat-LICENSE.txt`: bundled Python runtime uses Expat 2.8.3,
  https://raw.githubusercontent.com/libexpat/libexpat/R_2_8_3/expat/COPYING
- `libffi-LICENSE.txt`: https://raw.githubusercontent.com/libffi/libffi/v3.4.4/LICENSE

The release build copies all other runtime wheel licenses and native notices from
the actual installed distributions. It also copies Python's license, Tk's license,
and PyInstaller's bootloader license and exception.
