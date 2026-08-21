import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, TouchableOpacity, ActivityIndicator } from 'react-native';
import { listarFacturas } from '../services/server';

export default function FacturasScreen({ onSeleccionar, onVolver }) {
  const [cargando, setCargando] = useState(true);
  const [facturas, setFacturas] = useState([]);
  const [error, setError] = useState('');
  const [carpetaAbierta, setCarpetaAbierta] = useState(null);
  const [diaAbierto, setDiaAbierto] = useState(null);

  useEffect(() => {
    const cargar = async () => {
      try {
        const data = await listarFacturas();
        if (data.error) {
          setError(data.error);
        } else {
          setFacturas(data.facturas || []);
        }
      } catch (e) {
        setError('No se pudo conectar al servidor');
      }
      setCargando(false);
    };
    cargar();
  }, []);

  const agruparPorFecha = (pdfs) => {
    const grupos = {};
    pdfs.forEach(p => {
      const fecha = p.fecha || 'Sin fecha';
      if (!grupos[fecha]) grupos[fecha] = [];
      grupos[fecha].push(p);
    });
    return Object.entries(grupos).sort((a, b) => b[0].localeCompare(a[0]));
  };

  const pdfsAgrupados = agruparPorFecha(facturas);

  if (cargando) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#00d4ff" style={{ marginTop: 60 }} />
        <Text style={styles.vacio}>Cargando facturas...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.container}>
        <Text style={styles.titulo}>Facturas</Text>
        <Text style={styles.error}>{error}</Text>
        <TouchableOpacity style={styles.botonVolver} onPress={onVolver}>
          <Text style={styles.botonTexto}>Volver</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Seleccionar Factura</Text>
      <Text style={styles.subtitulo}>Facturas recientes (últimos 5 días)</Text>

      {pdfsAgrupados.length === 0 ? (
        <Text style={styles.vacio}>No hay facturas recientes</Text>
      ) : (
        <FlatList
          data={pdfsAgrupados}
          keyExtractor={([fecha]) => fecha}
          renderItem={({ item: [fecha, pdfs] }) => (
            <View style={styles_grupo.container}>
              <TouchableOpacity
                style={styles_grupo.header}
                onPress={() => setCarpetaAbierta(carpetaAbierta === fecha ? null : fecha)}
              >
                <Text style={styles_grupo.fecha}>{fecha}</Text>
                <Text style={styles_grupo.flecha}>{carpetaAbierta === fecha ? '▼' : '▶'}</Text>
              </TouchableOpacity>
              {carpetaAbierta === fecha && (
                <View style={styles_grupo.lista}>
                  {pdfs.map(pdf => (
                    <TouchableOpacity
                      key={pdf.nombre}
                      style={styles_grupo.item}
                      onPress={() => onSeleccionar(pdf.ruta, pdf.factura)}
                    >
                      <Text style={styles_grupo.itemNombre}>{pdf.nombre}</Text>
                      <Text style={styles_grupo.itemFactura}>{pdf.factura}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </View>
          )}
          style={styles.lista}
        />
      )}

      <TouchableOpacity style={styles.botonVolver} onPress={onVolver}>
        <Text style={styles.botonTexto}>Volver</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    paddingTop: 60,
    paddingHorizontal: 20,
  },
  titulo: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#00d4ff',
    textAlign: 'center',
    marginBottom: 4,
  },
  subtitulo: {
    fontSize: 13,
    color: '#888',
    textAlign: 'center',
    marginBottom: 16,
  },
  lista: {
    flex: 1,
  },
  vacio: {
    color: '#666',
    textAlign: 'center',
    marginTop: 40,
    fontSize: 14,
  },
  error: {
    color: '#e74c3c',
    textAlign: 'center',
    marginTop: 40,
    fontSize: 14,
  },
  botonVolver: {
    backgroundColor: '#e74c3c',
    paddingVertical: 14,
    paddingHorizontal: 40,
    borderRadius: 12,
    alignSelf: 'center',
    marginBottom: 40,
    marginTop: 10,
  },
  botonTexto: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
});

const styles_grupo = StyleSheet.create({
  container: {
    marginBottom: 8,
    backgroundColor: '#16213e',
    borderRadius: 8,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  fecha: {
    color: '#00d4ff',
    fontSize: 15,
    fontWeight: 'bold',
  },
  flecha: {
    color: '#888',
    fontSize: 14,
  },
  lista: {
    paddingHorizontal: 8,
    paddingBottom: 8,
  },
  item: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#0f3460',
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 6,
    marginBottom: 4,
  },
  itemNombre: {
    color: '#eee',
    fontSize: 13,
    flex: 1,
  },
  itemFactura: {
    color: '#00ff88',
    fontSize: 13,
    fontWeight: 'bold',
    marginLeft: 10,
  },
});
