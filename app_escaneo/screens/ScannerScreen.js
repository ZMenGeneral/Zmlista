import React, { useState, useEffect, useRef, useCallback } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, Vibration } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';

export default function ScannerScreen({ onEscaneado, onVolver, piezaActual, codigoPendiente }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [ultimoCodigo, setUltimoCodigo] = useState('');
  const [contador, setContador] = useState(0);
  const [puedeEscanear, setPuedeEscanear] = useState(false);
  const procesandoRef = useRef(false);

  useEffect(() => {
    if (permission && !permission.granted) {
      requestPermission();
    }
  }, [permission]);

  const handleBarcodeScanned = useCallback(({ type, data }) => {
    if (procesandoRef.current) return;
    procesandoRef.current = true;
    setPuedeEscanear(false);

    Vibration.vibrate(100);
    setUltimoCodigo(data);
    setContador(c => c + 1);
    onEscaneado(data);

    setTimeout(() => {
      procesandoRef.current = false;
    }, 1000);
  }, [onEscaneado]);

  const capturar = () => {
    setPuedeEscanear(true);
  };

  if (!permission) {
    return (
      <View style={styles.permisoContainer}>
        <Text style={styles.permisoTexto}>Solicitando permiso de camara...</Text>
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.permisoContainer}>
        <Text style={styles.permisoTexto}>Se necesita acceso a la camara</Text>
        <TouchableOpacity style={styles.botonPermiso} onPress={requestPermission}>
          <Text style={styles.botonTexto}>Dar permiso</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.botonVolver} onPress={onVolver}>
          <Text style={styles.botonTexto}>Volver</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        onBarcodeScanned={puedeEscanear ? handleBarcodeScanned : undefined}
        barcodeScannerSettings={{
          barcodeTypes: ['code128', 'code39', 'ean13', 'upc_a', 'qr'],
        }}
      >
        <View style={styles.overlay}>
          <View style={styles.frame} />

          <View style={styles.infoBar}>
            <Text style={styles.contador}>Escaneados: {contador}</Text>
            {piezaActual ? (
              <Text style={styles.piezaConfirmada}>✓ {piezaActual}</Text>
            ) : codigoPendiente ? (
              <Text style={styles.pendiente}>Sin asociar - elige una pieza</Text>
            ) : ultimoCodigo ? (
              <Text style={styles.ultimo}>Ultimo: {ultimoCodigo}</Text>
            ) : null}
          </View>

          <View style={styles.bottomRow}>
            <TouchableOpacity style={styles.botonVolver} onPress={onVolver}>
              <Text style={styles.botonTexto}>Volver</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.botonCaptura, puedeEscanear && styles.botonCapturando]}
              onPress={capturar}
              disabled={puedeEscanear}
            >
              <View style={styles.botonCapturaInner} />
            </TouchableOpacity>

            <View style={{ width: 80 }} />
          </View>
        </View>
      </CameraView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  camera: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: 40,
  },
  frame: {
    width: 280,
    height: 200,
    borderWidth: 2,
    borderColor: '#00d4ff',
    borderRadius: 12,
    marginTop: 80,
    backgroundColor: 'transparent',
  },
  infoBar: {
    backgroundColor: 'rgba(0,0,0,0.7)',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    alignItems: 'center',
    gap: 4,
  },
  contador: {
    color: '#00ff88',
    fontSize: 18,
    fontWeight: 'bold',
  },
  ultimo: {
    color: '#fff',
    fontSize: 12,
  },
  piezaConfirmada: {
    color: '#00ff88',
    fontSize: 14,
    fontWeight: 'bold',
  },
  pendiente: {
    color: '#f39c12',
    fontSize: 13,
    fontWeight: '600',
  },
  bottomRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    paddingHorizontal: 20,
  },
  botonCaptura: {
    width: 70,
    height: 70,
    borderRadius: 35,
    borderWidth: 4,
    borderColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  botonCapturando: {
    borderColor: '#00ff88',
    backgroundColor: 'rgba(0,255,136,0.3)',
  },
  botonCapturaInner: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#fff',
  },
  botonVolver: {
    backgroundColor: '#e74c3c',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 12,
    width: 80,
    alignItems: 'center',
  },
  botonPermiso: {
    backgroundColor: '#0f3460',
    paddingVertical: 14,
    paddingHorizontal: 40,
    borderRadius: 12,
  },
  botonTexto: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  permisoContainer: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 20,
  },
  permisoTexto: {
    color: '#eee',
    fontSize: 16,
  },
});
