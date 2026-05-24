import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../api_config.dart';

import 'package:intl/intl.dart';
import 'package:image_picker/image_picker.dart';
import 'current_user.dart';
import 'login_page.dart';

class ChauffeurDashboard extends StatefulWidget {
  final int driverId;
  final String userEmail;

  ChauffeurDashboard({required this.driverId, required this.userEmail});

  @override
  _ChauffeurDashboardState createState() => _ChauffeurDashboardState();
}

class _ChauffeurDashboardState extends State<ChauffeurDashboard> {
  int _selectedIndex = 0;
  List assignments = [];
  List reviews = [];
  Map<String, dynamic> driverStats = {};
  bool isLoading = true;
  bool _isPickingImage = false;


  @override
  void initState() {
    super.initState();
    fetchAllData();
  }

Future<void> fetchAllData() async {
  // 1. نجيبوا السفرات (هذي تخدم عندك مريغلة)
  try {
    await fetchAssignments();
  } catch (e) {
    print("Erreur Assignments: $e");
  }

  // 2. نجيبوا التقييمات (هذي اللي معطلة الحسبة)
  try {
    // نزيدوا await ونحطوها في try/catch وحدها باش كان فشلت ما تحبسش الصفحة
    await fetchReviews().timeout(Duration(seconds: 2)); 
    await fetchDriverStats().timeout(Duration(seconds: 2));
  } catch (e) {
    print("Stats non trouvés ou erreur: $e");
  }

  // 3. الخطوة السحرية: نحيو الـ Loading مهما كانت النتيجة
  if (mounted) {
    setState(() {
      isLoading = false; 
    });
  }
}

  Future<void> fetchAssignments() async {
    final response = await http.get(Uri.parse("${ApiConfig.baseUrl}/get_my_assignment/${widget.driverId}"));

    if (response.statusCode == 200) {
      setState(() => assignments = jsonDecode(response.body));
    }
  }

  Future<void> fetchReviews() async {
    final response = await http.get(Uri.parse("${ApiConfig.baseUrl}/get_driver_reviews/${widget.driverId}"));

    if (response.statusCode == 200) {
      setState(() => reviews = jsonDecode(response.body));
    }
  }

  Future<void> fetchDriverStats() async {
    final response = await http.get(Uri.parse("${ApiConfig.baseUrl}/get_driver_stats/${widget.driverId}"));

    if (response.statusCode == 200) {
      setState(() => driverStats = jsonDecode(response.body));
    }
  }

  // تسجيل البداية والنهاية في الـ Historique
  Future<void> handleAction(int parcoursId, String action, {String? depart, String? arrivee}) async {
    try {
      final response = await http.post(
        Uri.parse("${ApiConfig.baseUrl}/log_historique"),

        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "driver_id": widget.driverId,
          "parcours_id": parcoursId,
          "action": action,
          "depart": depart,
          "arrivee": arrivee,
          "timestamp": DateFormat('yyyy-MM-dd HH:mm:ss').format(DateTime.now()),
        }),
      );
      
      if (response.statusCode == 201) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Parcours $action ✅"), backgroundColor: Colors.green)
        );
      } else {
        var errorData = jsonDecode(response.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Erreur: ${errorData['error']}"), backgroundColor: Colors.red)
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Erreur de connexion au serveur ❌"), backgroundColor: Colors.red)
      );
    }
  }

  Future<void> _pickImage() async {
    if (_isPickingImage) return;
    _isPickingImage = true;

    try {
      final ImagePicker picker = ImagePicker();
      final XFile? pickedFile = await picker.pickImage(
        source: ImageSource.gallery, 
        maxWidth: 512, 
        maxHeight: 512,
        imageQuality: 75,
      );
      if (pickedFile != null) {
        final bytes = await pickedFile.readAsBytes();
        String base64 = base64Encode(bytes);
        setState(() {
          CurrentUser.photo = base64;
        });
      }
    } catch (e) {
      debugPrint("Error picking image: $e");
    } finally {
      _isPickingImage = false;
    }
  }


  @override
  Widget build(BuildContext context) {
    List<Widget> _pages = [
      _buildParcoursTab(),
      _buildIncidentTab(),
      _buildReviewsTab(),
      _buildProfileTab(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text("Mon Espace Chauffeur"),
        backgroundColor: Colors.teal[800],
        actions: [
          IconButton(
            icon: Icon(Icons.power_settings_new),
            onPressed: () async {
              await CurrentUser.clearSession();
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (_) => const LoginPage()),
                (route) => false,
              );
            },
          )
        ],
      ),
      body: isLoading ? Center(child: CircularProgressIndicator()) : _pages[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        selectedItemColor: Colors.teal[800],
        unselectedItemColor: Colors.grey,
        type: BottomNavigationBarType.fixed,
        onTap: (index) => setState(() => _selectedIndex = index),
        items: [
          BottomNavigationBarItem(icon: Icon(Icons.directions_bus), label: "Parcours"),
          BottomNavigationBarItem(icon: Icon(Icons.warning), label: "Incident"),
          BottomNavigationBarItem(icon: Icon(Icons.star), label: "Avis"),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: "Profil"),
        ],
      ),
    );
  }

  // 1. واجهة السفرات (Consultation + Démarrer/Arrêter)
  Widget _buildParcoursTab() {
    return Column(
      children: [
        Container(
          padding: EdgeInsets.all(15),
          width: double.infinity,
          color: Colors.teal[50],
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text("Mes Lignes Assignées:", style: TextStyle(fontSize: 12, color: Colors.teal[700])),
              Text(
                assignments.isNotEmpty 
                  ? assignments.map((a) => a['Libelle']).toSet().join(" | ") 
                  : 'Aucune ligne assignée', 
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.teal[900])
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: assignments.length,
            itemBuilder: (context, index) {
              var p = assignments[index];
              bool hasTrip = p['ID_parcours'] != null;

              return Card(
                margin: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                elevation: 2,
                child: ListTile(
                  leading: Icon(Icons.location_on, color: hasTrip ? Colors.teal : Colors.grey),
                  title: Text(
                    hasTrip ? "${p['Depart']} ➔ ${p['Arrivee']}" : "Aucun trajet programmé", 
                    style: TextStyle(fontWeight: FontWeight.bold, color: hasTrip ? Colors.black : Colors.grey)
                  ),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("Ligne: ${p['Libelle']}", style: TextStyle(fontSize: 12, color: Colors.teal)),
                      if (hasTrip) Text("Horaire: ${p['Heure_depart']} - ${p['Heure_arrivee']}"),
                    ],
                  ),
                  trailing: !hasTrip ? null : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (p['Statut'] == 'Pas démarré')
                        IconButton(
                          icon: Icon(Icons.play_circle_fill, color: Colors.green), 
                          onPressed: () async {
                            await handleAction(p['ID_parcours'], "Début", depart: p['Depart'], arrivee: p['Arrivee']);
                            fetchAssignments();
                          }
                        ),
                      if (p['Statut'] == 'En cours')
                        IconButton(
                          icon: Icon(Icons.stop_circle, color: Colors.red), 
                          onPressed: () async {
                            await handleAction(p['ID_parcours'], "Fin");
                            fetchAssignments();
                          }
                        ),
                      if (p['Statut'] == 'Terminé')
                        Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.check_circle, color: Colors.blue),
                            Text("Terminé", style: TextStyle(color: Colors.blue, fontSize: 10)),
                          ],
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  // 2. واجهة الإبلاغ عن حادث
  Widget _buildIncidentTab() {
    TextEditingController desc = TextEditingController();
    return Padding(
      padding: EdgeInsets.all(20),
      child: Column(
        children: [
          TextField(controller: desc, decoration: InputDecoration(labelText: "Description de l'incident"), maxLines: 3),
          SizedBox(height: 20),
          ElevatedButton(
            onPressed: () async {
              await http.post(Uri.parse("${ApiConfig.baseUrl}/declare_incident"),
                headers: {"Content-Type": "application/json"},
                body: jsonEncode({"driver_id": widget.driverId, "description": desc.text, "timestamp": DateTime.now().toString()}));
              desc.clear();
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Signalé au central 🚨")));
            },
            child: Text("Déclarer l'incident"),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.orange[800], foregroundColor: Colors.white),
          )
        ],
      ),
    );
  }

  // 3. واجهة التقييمات
  Widget _buildReviewsTab() {
    return reviews.isEmpty 
    ? Center(child: Text("Pas encore d'avis clients"))
    : ListView.builder(
        itemCount: reviews.length,
        itemBuilder: (context, index) {
          var r = reviews[index];
          String sentiment = r['sentiment'] ?? "Neutre";
          Color sColor = sentiment == "Positif" ? Colors.green : (sentiment == "Négatif" ? Colors.red : Colors.orange);

          return Card(
            margin: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            child: ListTile(
              leading: Icon(Icons.star, color: Colors.amber),
              title: Text(r['commentaire']),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("Note: ${r['note']}/5"),
                  Row(
                    children: [
                      Container(
                        padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(color: sColor.withOpacity(0.1), borderRadius: BorderRadius.circular(5)),
                        child: Text(sentiment, style: TextStyle(color: sColor, fontSize: 10, fontWeight: FontWeight.bold)),
                      ),
                      if (r['category'] != null) ...[
                        SizedBox(width: 8),
                        Text("📌 ${r['category']}", style: TextStyle(fontSize: 10, color: Colors.grey[600])),
                      ]
                    ],
                  ),
                ],
              ),
            ),
          );
        }
      );
  }

  // 4. واجهة البروفايل (Premium Update Version)
  Widget _buildProfileTab() {
    final TextEditingController nameCtrl = TextEditingController(text: CurrentUser.nom);
    final TextEditingController emailCtrl = TextEditingController(text: widget.userEmail);
    final TextEditingController passCtrl = TextEditingController();
    
    // Logic for photo
    String? localPhoto = CurrentUser.photo;

    return SingleChildScrollView(
      padding: EdgeInsets.all(20),
      child: Column(
        children: [
          GestureDetector(
            onTap: _pickImage,
            child: Stack(
              children: [
                CircleAvatar(
                  radius: 50,
                  backgroundColor: Colors.teal[800],
                  backgroundImage: CurrentUser.photo.isNotEmpty 
                      ? MemoryImage(base64Decode(CurrentUser.photo)) 
                      : null,
                  child: CurrentUser.photo.isEmpty 
                      ? Icon(Icons.person, color: Colors.white, size: 50) 
                      : null,
                ),
                Positioned(
                  bottom: 0,
                  right: 0,
                  child: Container(
                    padding: EdgeInsets.all(4),
                    decoration: BoxDecoration(color: Colors.orange, shape: BoxShape.circle),
                    child: Icon(Icons.camera_alt, color: Colors.white, size: 15),
                  ),
                ),
              ],
            ),
          ),
          SizedBox(height: 20),
          if (driverStats.isNotEmpty) ...[
            Container(
              padding: EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [Colors.teal[800]!, Colors.teal[600]!]),
                borderRadius: BorderRadius.circular(15),
                boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 8)],
              ),
              child: Column(
                children: [
                  Text("Score de Performance", style: TextStyle(color: Colors.white70, fontSize: 12)),
                  Text(
                    "${driverStats['performance_score'] ?? 5.0} / 5",
                    style: TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold),
                  ),
                  Divider(color: Colors.white24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _buildMiniStat("Incidents", "${driverStats['incident_count'] ?? 0}"),
                      _buildMiniStat("Avis", "${reviews.length}"),
                    ],
                  )
                ],
              ),
            ),
          ],
          SizedBox(height: 25),
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
            elevation: 4,
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("Paramètres du compte", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.teal[800])),
                  SizedBox(height: 20),
                  TextField(
                    controller: nameCtrl,
                    decoration: InputDecoration(
                      labelText: "Nom",
                      prefixIcon: Icon(Icons.person_outline),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  SizedBox(height: 15),
                  TextField(
                    controller: emailCtrl,
                    decoration: InputDecoration(
                      labelText: "Email",
                      prefixIcon: Icon(Icons.email_outlined),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  SizedBox(height: 15),
                  TextField(
                    controller: passCtrl,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: "Nouveau mot de passe",
                      hintText: "Laisser vide si inchangé",
                      prefixIcon: Icon(Icons.lock_outline),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  SizedBox(height: 25),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () async {
                        final res = await http.post(
                          Uri.parse("${ApiConfig.baseUrl}/update_profile"),

                          headers: {"Content-Type": "application/json"},
                          body: jsonEncode({
                            "user_id": CurrentUser.id,
                            "name": nameCtrl.text,
                            "email": emailCtrl.text,
                            "password": passCtrl.text.isEmpty ? null : passCtrl.text,
                            "photo": CurrentUser.photo,
                          }),
                        );
                        if (res.statusCode == 200) {
                          await CurrentUser.saveSession(emailCtrl.text, CurrentUser.role, CurrentUser.id, userNom: nameCtrl.text, userPhoto: CurrentUser.photo);
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Profil mis à jour ✅"), backgroundColor: Colors.green));
                          passCtrl.clear();
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Erreur lors de la mise à jour"), backgroundColor: Colors.red));
                        }
                      },
                      child: Text("METTRE À JOUR"),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.teal[800],
                        foregroundColor: Colors.white,
                        padding: EdgeInsets.symmetric(vertical: 15),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          SizedBox(height: 20),
          TextButton.icon(
            onPressed: () async {
              await CurrentUser.clearSession();
              Navigator.pushAndRemoveUntil(context, MaterialPageRoute(builder: (_) => const LoginPage()), (route) => false);
            },
            icon: Icon(Icons.logout, color: Colors.red),
            label: Text("DÉCONNEXION", style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
          ),
          SizedBox(height: 30),
        ],
      ),
    );
  }

  Widget _buildMiniStat(String label, String value) {
    return Column(
      children: [
        Text(value, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        Text(label, style: TextStyle(color: Colors.white70, fontSize: 10)),
      ],
    );
  }
}