import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../api_config.dart';


class IncidentListPage extends StatefulWidget {
  @override
  _IncidentListPageState createState() => _IncidentListPageState();
}

class _IncidentListPageState extends State<IncidentListPage> {
  List incidents = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchIncidents();
  }

  // جلب قائمة الحوادث
  Future<void> fetchIncidents() async {
    setState(() => isLoading = true);
    try {
      final response = await http.get(Uri.parse('${ApiConfig.baseUrl}/get_all_incidents'));

      if (response.statusCode == 200) {
        setState(() {
          incidents = json.decode(response.body);
          isLoading = false;
        });
      }
    } catch (e) {
      print("Erreur: $e");
      setState(() => isLoading = false);
    }
  }

  // دالة لتحديث حالة الحادث (Action)
  Future<void> updateIncidentStatus(int id, String newStatus, int isCritique) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/update_incident_status/$id'),

        headers: {"Content-Type": "application/json"},
        body: json.encode({
          "Statut": newStatus,
          "Critique": isCritique,
        }),
      );
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Action enregistrée ✅")));
        fetchIncidents(); // تحديث القائمة بعد التعديل
      }
    } catch (e) {
      print("Erreur update: $e");
    }
  }

  // نافذة الخيارات (Bottom Sheet)
  void _showActionMenu(Map incident) {
    showModalBottomSheet(
      context: context,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(25))),
      builder: (context) {
        return Container(
          padding: EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(width: 50, height: 5, decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(10))),
              SizedBox(height: 15),
              Text("Actions - Incident #${incident['ID_incident']}", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              Divider(),
              
              // 1. Consulter
              ListTile(
                leading: Icon(Icons.info_outline, color: Colors.blue),
                title: Text("Consulter les détails"),
                onTap: () {
                  Navigator.pop(context);
                  _showDetailsDialog(incident);
                },
              ),
              
              // 2. Mettre à jour le statut
              ListTile(
                leading: Icon(Icons.check_circle_outline, color: Colors.green),
                title: Text("Marquer comme Résolu"),
                onTap: () {
                  Navigator.pop(context);
                  updateIncidentStatus(incident['ID_incident'], "Résolu", 0);
                },
              ),
              
              // 3. Marquer comme Critique
              ListTile(
                leading: Icon(Icons.error_outline, color: Colors.red),
                title: Text("Marquer comme CRITIQUE", style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                onTap: () {
                  Navigator.pop(context);
                  updateIncidentStatus(incident['ID_incident'], "En cours", 1);
                },
              ),

              // 4. Supprimer
              ListTile(
                leading: Icon(Icons.delete_outline, color: Colors.red),
                title: Text("Supprimer l'alerte", style: TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.pop(context);
                  _confirmDeletion(incident['ID_incident']);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  // تأكيد الحذف
  void _confirmDeletion(int id) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text("Confirmer la suppression"),
        content: Text("Voulez-vous vraiment supprimer cette alerte ?"),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text("Annuler")),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              deleteIncident(id);
            },
            child: Text("Supprimer", style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  Future<void> deleteIncident(int id) async {
    try {
      final response = await http.delete(Uri.parse('${ApiConfig.baseUrl}/delete_incident/$id'));
      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Alerte supprimée 🗑️")));
        fetchIncidents();
      }
    } catch (e) {
      print("Erreur delete: $e");
    }
  }

  // نافذة عرض التفاصيل الكاملة
  void _showDetailsDialog(Map incident) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text("Détails de l'incident"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("📍 Parcours: ${incident['Nom_Ligne'] ?? 'N/A'}", style: TextStyle(fontWeight: FontWeight.bold)),
            Text("🚌 Bus Numero: ${incident['Numero_bus'] ?? 'Non assigné'}"),
            Text("🕒 Date: ${incident['Date']}"),
            Text("📝 Description: ${incident['Description']}"),
            SizedBox(height: 10),
            // ✅ صحيح
            Text(
  "Statut actuel: ${incident['Statut'] ?? 'Nouveau'}", 
  style: TextStyle(color: Colors.orange), // 👈 هوني يتحط اللون
),
             ],
             ),
             actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text("Fermer"))],
            ),
              );
             }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Gestion des Incidents", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.orange[800],
        elevation: 0,
      ),
      body: isLoading 
          ? Center(child: CircularProgressIndicator(color: Colors.orange))
          : RefreshIndicator(
              onRefresh: fetchIncidents,
              child: incidents.isEmpty 
                  ? Center(child: Text("Aucun incident à traiter"))
                  : ListView.builder(
                      itemCount: incidents.length,
                      itemBuilder: (context, index) {
                        final incident = incidents[index];
                        // تحديد اللون حسب الخطورة
                        bool isCritique = incident['Performance_IA'] == 1;

                        return Card(
                          margin: EdgeInsets.symmetric(horizontal: 15, vertical: 8),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(15),
                            side: BorderSide(color: isCritique ? Colors.red : Colors.transparent, width: 2),
                          ),
                          child: ListTile(
                            onTap: () => _showActionMenu(incident), // يحل المنيو عند النقر
                            leading: CircleAvatar(
                              backgroundColor: isCritique ? Colors.red : Colors.orange[100],
                              child: Icon(isCritique ? Icons.priority_high : Icons.warning, color: isCritique ? Colors.white : Colors.orange[900]),
                            ),
                            title: Text("Bus N°: ${incident['Numero_bus'] ?? 'Non assigné'}", style: TextStyle(fontWeight: FontWeight.bold)),
                            subtitle: Text(incident['Description'], maxLines: 1, overflow: TextOverflow.ellipsis),
                            trailing: Icon(Icons.more_vert),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}