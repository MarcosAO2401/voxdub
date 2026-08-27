#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("voxdub-backend")
                .expect("no se encontró el binario del backend (voxdub-backend)");
            let _child = sidecar
                .spawn()
                .expect("no se pudo iniciar el backend de VoxDub");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error mientras se ejecutaba VoxDub");
}
