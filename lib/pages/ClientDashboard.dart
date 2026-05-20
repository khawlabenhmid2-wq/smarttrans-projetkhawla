import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../api_config.dart';


import 'Clienthistorique_page.dart';
import 'login_page.dart';
import 'profile_page.dart';
import 'current_user.dart';


class ClientDashboard extends StatefulWidget {
  final int clientId;
  final String userEmail;

  const ClientDashboard({
    super.key,
    required this.clientId,
    required this.userEmail,
  });

  @override
  State<ClientDashboard> createState() => _ClientDashboardState();
}

class _ClientDashboardState extends State<ClientDashboard> {
  List lignes = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchLignes();
  }

  Future<void> fetchLignes() async {
    const url = "${ApiConfig.baseUrl}/get_client_trips";


    try {
      final res = await http.get(Uri.parse(url));

      if (res.statusCode == 200) {
        setState(() {
          lignes = jsonDecode(res.body);
          isLoading = false;
        });
      }
    } catch (e) {
      debugPrint(e.toString());
      setState(() => isLoading = false);
    }
  }

  void showAvisDialog(int idHistorique) {
    TextEditingController commentCtrl = TextEditingController();
    int rating = 3;

    showDialog(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (context, setStateDialog) {
          return AlertDialog(
            title: const Text("Ajouter un avis"),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: commentCtrl,
                  decoration: const InputDecoration(
                    hintText: "Commentaire...",
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 15),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    5,
                    (index) => IconButton(
                      icon: Icon(
                        Icons.star,
                        color: index < rating
                            ? Colors.orange
                            : Colors.grey,
                      ),
                      onPressed: () {
                        setStateDialog(() {
                          rating = index + 1;
                        });
                      },
                    ),
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text("Annuler"),
              ),
              ElevatedButton(
                onPressed: () async {
                  const url = "${ApiConfig.baseUrl}/add_avis";


                  await http.post(
                    Uri.parse(url),
                    headers: {"Content-Type": "application/json"},
                    body: jsonEncode({
                      "client_id": widget.clientId,
                      "id_historique": idHistorique,
                      "commentaire": commentCtrl.text,
                      "note": rating,
                    }),
                  );

                  Navigator.pop(context);

                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Avis ajouté")),
                  );
                },
                child: const Text("Envoyer"),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget buildDrawer() {
    return Drawer(
      child: ListView(
        children: [
          UserAccountsDrawerHeader(
            decoration: const BoxDecoration(color: Colors.teal),
            accountName: const Text(''),
            accountEmail: Text(widget.userEmail),
            currentAccountPicture: const CircleAvatar(
              backgroundColor: Colors.white,
              child: Icon(Icons.person, color: Colors.teal),
            ),
          ),

          ListTile(
            leading: const Icon(Icons.history),
            title: const Text("Historique"),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => HistoriquePage(
                    clientId: widget.clientId,
                  ),
                ),
              );
            },
          ),

          ListTile(
            leading: const Icon(Icons.person),
            title: const Text("Mon Profil"),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      ProfilePage (userEmail: widget.userEmail),
                ),
              );
            },
          ),



          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text("Déconnexion"),
            onTap: () async {
              await CurrentUser.clearSession();
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(
                  builder: (_) => const LoginPage(),
                ),
                (route) => false,
              );
            },
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      drawer: buildDrawer(),

      appBar: AppBar(
        title: const Text("Client Dashboard"),
        flexibleSpace: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Colors.teal, Colors.green],
            ),
          ),
        ),
      ),

      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _buildHeaderCards(),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.all(10),
                    itemCount: lignes.length,
                    itemBuilder: (context, index) {
                      final ligne = lignes[index];
                      final rides = ligne['rides'] ?? [];

                      return Card(
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: ExpansionTile(
                          leading: const Icon(Icons.directions_bus),
                          title: Text(ligne['libelle'] ?? ''),
                          subtitle: Text(ligne['description'] ?? ''),
                          children: [
                            Padding(
                              padding: const EdgeInsets.all(10),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text("Bus: ${ligne['code_bus'] ?? ''}"),
                                  const SizedBox(height: 10),
                                  rides.isEmpty
                                      ? const Text(
                                          "Aucun trajet effectué pour le moment",
                                          style: TextStyle(
                                              fontSize: 12, color: Colors.grey))
                                      : Column(
                                          children: List.generate(
                                            rides.length,
                                            (i) {
                                              final r = rides[i];

                                              return ListTile(
                                                title: Text(
                                                  "${r['Depart'] ?? ''} ➜ ${r['Arrivee'] ?? ''}",
                                                  style: const TextStyle(
                                                      fontWeight: FontWeight.w500),
                                                ),
                                                subtitle: Text(
                                                    "Date: ${r['Date'] ?? ''} | Chauffeur: ${r['Nom_Chauffeur'] ?? ''}",
                                                    style: const TextStyle(
                                                        fontSize: 11)),
                                                trailing: IconButton(
                                                  icon: const Icon(
                                                    Icons.star,
                                                    color: Colors.orange,
                                                  ),
                                                  onPressed: () {
                                                    showAvisDialog(
                                                        r['ID_historique']);
                                                  },
                                                ),
                                              );
                                            },
                                          ),
                                        ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildHeaderCards() {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Row(
        children: [
          Expanded(
            child: _buildStatCard(
              "Mes Lignes",
              lignes.length.toString(),
              Icons.map,
              Colors.teal,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String count, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(15),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Row(
        children: [
          Icon(icon, size: 30, color: color),
          const SizedBox(width: 10),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  count,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  title,
                  style: TextStyle(
                    color: Colors.grey[600],
                    fontSize: 12,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}