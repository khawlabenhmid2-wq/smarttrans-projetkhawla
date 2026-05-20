import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../api_config.dart';

import 'package:intl/intl.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class AdminAddParcoursPage extends StatefulWidget {
  @override
  _AdminAddParcoursPageState createState() => _AdminAddParcoursPageState();
}

class _AdminAddParcoursPageState extends State<AdminAddParcoursPage> {
  List lignes = [];
  String? selectedLigne;

  TextEditingController departController = TextEditingController();
  TextEditingController arriveeController = TextEditingController();

  // 6 time slots
  List<TextEditingController> heureControllers =
      List.generate(6, (index) => TextEditingController());

  bool isLoadingLignes = true;

  // Map Variables
  LatLng? departCoord;
  LatLng? arriveeCoord;
  String pickingMode = 'depart';
  final MapController mapController = MapController();
  static const LatLng _center = LatLng(33.8828, 10.0982);

  // Autocomplete suggestions
  List<Map<String, dynamic>> departSuggestions = [];
  List<Map<String, dynamic>> arriveeSuggestions = [];
  bool showDepartSuggestions = false;
  bool showArriveeSuggestions = false;
  Timer? _debounceTimer;

  @override
  void initState() {
    super.initState();
    fetchLignes();
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    departController.dispose();
    arriveeController.dispose();
    for (final c in heureControllers) c.dispose();
    super.dispose();
  }

  // Add 1 hour in 24h format
  String addOneHour24h(String startTime) {
    try {
      DateFormat format24 = DateFormat("HH:mm");
      DateTime dateTime = format24.parse(startTime.trim());
      DateTime arrivalTime = dateTime.add(const Duration(hours: 1));
      return format24.format(arrivalTime);
    } catch (e) {
      return startTime;
    }
  }

  Future<void> fetchLignes() async {
    try {
      final response =
          await http.get(Uri.parse('${ApiConfig.baseUrl}/get_lignes'));
      if (response.statusCode == 200) {
        setState(() {
          lignes = json.decode(response.body);
          isLoadingLignes = false;
        });
      }
    } catch (e) {
      setState(() => isLoadingLignes = false);
    }
  }

  // ── Nominatim autocomplete ──────────────────────────────────────────────────
  Future<void> _fetchSuggestions(String query, bool isDepart) async {
    if (query.length < 3) {
      setState(() {
        if (isDepart) {
          departSuggestions = [];
          showDepartSuggestions = false;
        } else {
          arriveeSuggestions = [];
          showArriveeSuggestions = false;
        }
      });
      return;
    }

    try {
      final response = await http.get(
        Uri.parse(
            'https://nominatim.openstreetmap.org/search?format=json&q=${Uri.encodeComponent("$query, Gabès")}&limit=8&addressdetails=1&accept-language=fr&countrycodes=tn&viewbox=9.7,33.7,10.4,34.1&bounded=1'),
        headers: {
          'User-Agent': 'SmartTransApp/1.0 (com.example.smart_trans_v2)'
        },
      );

      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        final suggestions = data.map<Map<String, dynamic>>((item) {
          final addr = item['address'] as Map<String, dynamic>? ?? {};
          // Build a meaningful short name from address components
          final name = item['name'] as String? ?? '';
          final road = addr['road'] as String? ?? '';
          final neighbourhood = addr['neighbourhood'] as String? ??
              addr['suburb'] as String? ?? '';
          final city = addr['city'] as String? ??
              addr['town'] as String? ??
              addr['village'] as String? ??
              addr['county'] as String? ?? '';
          String shortName;
          if (name.isNotEmpty && city.isNotEmpty && name != city) {
            shortName = "$name, $city";
          } else if (road.isNotEmpty && city.isNotEmpty) {
            shortName = neighbourhood.isNotEmpty
                ? "$road, $neighbourhood, $city"
                : "$road, $city";
          } else {
            final parts = (item['display_name'] as String).split(',');
            shortName = parts.length >= 2
                ? "${parts[0].trim()}, ${parts[1].trim()}"
                : parts[0].trim();
          }
          return {
            'short': shortName,
            'full': item['display_name'],
            'lat': double.parse(item['lat']),
            'lon': double.parse(item['lon']),
          };
        }).toList();

        setState(() {
          if (isDepart) {
            departSuggestions = suggestions;
            showDepartSuggestions = suggestions.isNotEmpty;
          } else {
            arriveeSuggestions = suggestions;
            showArriveeSuggestions = suggestions.isNotEmpty;
          }
        });
      }
    } catch (e) {
      // silently fail
    }
  }

  void _onSuggestionSelected(Map<String, dynamic> suggestion, bool isDepart) {
    final point = LatLng(suggestion['lat'], suggestion['lon']);
    setState(() {
      if (isDepart) {
        departController.text = suggestion['short'];
        departCoord = point;
        departSuggestions = [];
        showDepartSuggestions = false;
      } else {
        arriveeController.text = suggestion['short'];
        arriveeCoord = point;
        arriveeSuggestions = [];
        showArriveeSuggestions = false;
      }
    });
    mapController.move(point, 16.0);
  }
  // ───────────────────────────────────────────────────────────────────────────

  Future<void> saveParcours() async {
    if (selectedLigne == null ||
        departController.text.isEmpty ||
        arriveeController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Veuillez remplir tous les champs")),
      );
      return;
    }

    if (departController.text.trim().toLowerCase() ==
        arriveeController.text.trim().toLowerCase()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text("Le départ et l'arrivée doivent être différents ❌"),
            backgroundColor: Colors.orange),
      );
      return;
    }

    int count = 0;
    for (int i = 0; i < heureControllers.length; i++) {
      if (heureControllers[i].text.isNotEmpty) {
        String arrivalTime;
        if (i < heureControllers.length - 1 &&
            heureControllers[i + 1].text.isNotEmpty) {
          arrivalTime = heureControllers[i + 1].text;
        } else {
          arrivalTime = addOneHour24h(heureControllers[i].text);
        }

        String currentDepart =
            (i % 2 == 0) ? departController.text : arriveeController.text;
        String currentArrivee =
            (i % 2 == 0) ? arriveeController.text : departController.text;

        final response = await http.post(
          Uri.parse('${ApiConfig.baseUrl}/add_parcours'),
          headers: {"Content-Type": "application/json"},
          body: json.encode({
            "Depart": currentDepart,
            "Arrivee": currentArrivee,
            "Heure_depart": heureControllers[i].text,
            "Heure_arrivee": arrivalTime,
            "Code_Ligne": selectedLigne,
            "Etat": 0,
          }),
        );
        if (response.statusCode == 201) count++;
      }
    }

    if (count > 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text("$count Trajets enregistrés (Aller/Retour) ✅"),
            backgroundColor: Colors.green),
      );
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Programmation des Parcours",
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.teal[700],
      ),
      body: Container(
        color: Colors.grey[100],
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSectionTitle("Informations de la Ligne"),
              Card(
                elevation: 3,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(15)),
                child: Padding(
                  padding: const EdgeInsets.all(15),
                  child: Column(
                    children: [
                      isLoadingLignes
                          ? const CircularProgressIndicator()
                          : DropdownButtonFormField<String>(
                              value: selectedLigne,
                              decoration: InputDecoration(
                                labelText: "Choisir une Ligne",
                                prefixIcon:
                                    const Icon(Icons.route, color: Colors.teal),
                                border: OutlineInputBorder(
                                    borderRadius: BorderRadius.circular(10)),
                              ),
                              items: lignes
                                  .map((l) => DropdownMenuItem<String>(
                                        value: l['Code_Ligne'].toString(),
                                        child: Text(l['Libelle'] ?? "Ligne"),
                                      ))
                                  .toList(),
                              onChanged: (val) =>
                                  setState(() => selectedLigne = val),
                            ),
                      const SizedBox(height: 15),
                      _buildTextField(
                        departController,
                        "Point de Départ",
                        Icons.location_on,
                        isDepart: true,
                      ),
                      const SizedBox(height: 15),
                      _buildTextField(
                        arriveeController,
                        "Point d'Arrivée",
                        Icons.flag,
                        isDepart: false,
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 20),
              _buildSectionTitle("Choisir sur la Carte (Gabès)"),
              Card(
                elevation: 4,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(15)),
                child: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          ChoiceChip(
                            label: const Text("Départ"),
                            selected: pickingMode == 'depart',
                            onSelected: (val) =>
                                setState(() => pickingMode = 'depart'),
                            selectedColor: Colors.teal.withOpacity(0.3),
                          ),
                          ChoiceChip(
                            label: const Text("Arrivée"),
                            selected: pickingMode == 'arrivee',
                            onSelected: (val) =>
                                setState(() => pickingMode = 'arrivee'),
                            selectedColor: Colors.red.withOpacity(0.3),
                          ),
                        ],
                      ),
                    ),

                    SizedBox(
                      height: 300,
                      child: ClipRRect(
                        borderRadius: const BorderRadius.only(
                          bottomLeft: Radius.circular(15),
                          bottomRight: Radius.circular(15),
                        ),
                        child: FlutterMap(
                          mapController: mapController,
                          options: MapOptions(
                            center: _center,
                            zoom: 15.0,
                            maxZoom: 19.0,
                            onTap: (tapPosition, point) {
                              setState(() {
                                if (pickingMode == 'depart') {
                                  departCoord = point;
                                  departController.text = "Chargement...";
                                  departSuggestions = [];
                                  showDepartSuggestions = false;
                                  _getAddressFromLatLng(point, true);
                                } else {
                                  arriveeCoord = point;
                                  arriveeController.text = "Chargement...";
                                  arriveeSuggestions = [];
                                  showArriveeSuggestions = false;
                                  _getAddressFromLatLng(point, false);
                                }
                              });
                            },
                          ),
                          nonRotatedChildren: [
                            RichAttributionWidget(
                              attributions: [
                                TextSourceAttribution('© CARTO'),
                                TextSourceAttribution('© OpenStreetMap'),
                              ],
                            ),
                          ],
                          children: [
                            TileLayer(
                              urlTemplate:
                                  'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                              userAgentPackageName:
                                  'com.example.smart_trans_v2',
                              maxZoom: 19,
                            ),
                            MarkerLayer(
                              markers: [
                                if (departCoord != null)
                                  Marker(
                                    point: departCoord!,
                                    width: 40,
                                    height: 40,
                                    child: const Icon(Icons.location_on,
                                        color: Colors.teal, size: 40),
                                  ),
                                if (arriveeCoord != null)
                                  Marker(
                                    point: arriveeCoord!,
                                    width: 40,
                                    height: 40,
                                    child: const Icon(Icons.flag,
                                        color: Colors.red, size: 40),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),

                    if (departCoord != null || arriveeCoord != null)
                      TextButton.icon(
                        onPressed: () => setState(() {
                          departCoord = null;
                          arriveeCoord = null;
                          departController.clear();
                          arriveeController.clear();
                          departSuggestions = [];
                          arriveeSuggestions = [];
                          showDepartSuggestions = false;
                          showArriveeSuggestions = false;
                        }),
                        icon: const Icon(Icons.refresh,
                            size: 16, color: Colors.grey),
                        label: const Text("Réinitialiser les points",
                            style:
                                TextStyle(color: Colors.grey, fontSize: 12)),
                      ),
                  ],
                ),
              ),

              const SizedBox(height: 25),
              _buildSectionTitle("Horaires (Format 24h)"),

              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                crossAxisSpacing: 15,
                mainAxisSpacing: 15,
                childAspectRatio: 4,
                children:
                    List.generate(6, (index) => _buildTimeField(index)),
              ),

              const SizedBox(height: 30),
              ElevatedButton(
                onPressed: saveParcours,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.teal[700],
                  minimumSize: const Size(double.infinity, 55),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text("ENREGISTRER LE PLANNING",
                    style: TextStyle(
                        fontSize: 16,
                        color: Colors.white,
                        fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10, left: 5),
      child: Text(title,
          style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.bold,
              color: Colors.teal[900])),
    );
  }

  Widget _buildTextField(
    TextEditingController controller,
    String label,
    IconData icon, {
    required bool isDepart,
  }) {
    final suggestions =
        isDepart ? departSuggestions : arriveeSuggestions;
    final showSuggestions =
        isDepart ? showDepartSuggestions : showArriveeSuggestions;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: controller,
          readOnly: false,
          onTap: () {
            setState(() {
              pickingMode = isDepart ? 'depart' : 'arrivee';
            });
          },
          onChanged: (value) {
            _debounceTimer?.cancel();
            _debounceTimer =
                Timer(const Duration(milliseconds: 400), () {
              _fetchSuggestions(value, isDepart);
            });
          },
          decoration: InputDecoration(
            labelText: label,
            prefixIcon: Icon(icon,
                color: isDepart ? Colors.teal : Colors.red),
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10)),
            filled: true,
            fillColor: Colors.white,
            suffixIcon: controller.text.isNotEmpty
                ? IconButton(
                    icon:
                        const Icon(Icons.clear, color: Colors.grey),
                    onPressed: () {
                      setState(() {
                        controller.clear();
                        if (isDepart) {
                          departCoord = null;
                          departSuggestions = [];
                          showDepartSuggestions = false;
                        } else {
                          arriveeCoord = null;
                          arriveeSuggestions = [];
                          showArriveeSuggestions = false;
                        }
                      });
                    },
                  )
                : const Icon(Icons.map, color: Colors.grey),
            helperText: "Saisissez ou choisissez sur la carte",
          ),
        ),
        // ── Suggestions dropdown ──────────────────────────────────
        if (showSuggestions && suggestions.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 2),
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: Colors.teal.shade200),
              borderRadius: BorderRadius.circular(8),
              boxShadow: const [
                BoxShadow(
                    color: Colors.black12,
                    blurRadius: 6,
                    offset: Offset(0, 3))
              ],
            ),
            child: ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: suggestions.length,
              separatorBuilder: (_, __) =>
                  Divider(height: 1, color: Colors.teal.shade50),
              itemBuilder: (context, i) {
                final s = suggestions[i];
                return ListTile(
                  dense: true,
                  leading: Icon(
                    isDepart ? Icons.location_on : Icons.flag,
                    color: isDepart ? Colors.teal : Colors.red,
                    size: 20,
                  ),
                  title: Text(s['short'],
                      style: const TextStyle(fontSize: 13)),
                  subtitle: Text(
                    s['full'],
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        fontSize: 11, color: Colors.grey[500]),
                  ),
                  onTap: () =>
                      _onSuggestionSelected(s, isDepart),
                );
              },
            ),
          ),
        // ─────────────────────────────────────────────────────────
      ],
    );
  }

  Future<void> _getAddressFromLatLng(LatLng point, bool isDepart) async {
    try {
      final response = await http.get(
        Uri.parse(
            'https://nominatim.openstreetmap.org/reverse?format=json&lat=${point.latitude}&lon=${point.longitude}&zoom=18'),
        headers: {
          'User-Agent': 'SmartTransApp/1.0 (com.example.smart_trans_v2)'
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        String address = data['display_name'] ?? "";
        List<String> parts = address.split(',');
        if (parts.length >= 2) {
          address = "${parts[0].trim()}, ${parts[1].trim()}";
        }
        setState(() {
          if (isDepart) {
            departController.text = address;
          } else {
            arriveeController.text = address;
          }
        });
      } else {
        _setCoords(point, isDepart);
      }
    } catch (e) {
      _setCoords(point, isDepart);
    }
  }

  void _setCoords(LatLng point, bool isDepart) {
    final coords =
        "${point.latitude.toStringAsFixed(4)}, ${point.longitude.toStringAsFixed(4)}";
    setState(() {
      if (isDepart) {
        departController.text = coords;
      } else {
        arriveeController.text = coords;
      }
    });
  }

  Widget _buildTimeField(int index) {
    return TextField(
      controller: heureControllers[index],
      readOnly: true,
      textAlign: TextAlign.center,
      decoration: InputDecoration(
        hintText: "Sprint ${index + 1}",
        prefixIcon:
            const Icon(Icons.access_time, size: 18, color: Colors.teal),
        border:
            OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        filled: true,
        fillColor: Colors.white,
      ),
      onTap: () async {
        TimeOfDay? picked = await showTimePicker(
          context: context,
          initialTime: TimeOfDay.now(),
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(alwaysUse24HourFormat: true),
            child: child!,
          ),
        );
        if (picked != null) {
          setState(() {
            heureControllers[index].text =
                picked.hour.toString().padLeft(2, '0') +
                    ":" +
                    picked.minute.toString().padLeft(2, '0');
          });
        }
      },
    );
  }
}