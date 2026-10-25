import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_widget_from_html/flutter_widget_from_html.dart';
import 'package:http/http.dart' as http;

const String baseUrl = 'http://127.0.0.1:8000';

void main() {
  runApp(const MevzuatTakipApp());
}

class MevzuatTakipApp extends StatelessWidget {
  const MevzuatTakipApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mevzuat Kütüphanesi & Takip',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E3A8A),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<dynamic> _mevzuatlar = [];
  List<dynamic> _oneriler = [];
  List<dynamic> _kelimeler = [];
  bool _isLoading = false;
  final TextEditingController _kelimeController = TextEditingController();

  // YENİ: Arama değişkenleri
  final TextEditingController _aramaController = TextEditingController();
  List<dynamic> _aramaSonuclari = [];
  bool _aramaYapiliyor = false;
  String _sonAramaTerimi = '';
  Timer? _aramaDebounce;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _fetchAllData();
  }

  @override
  void dispose() {
    _aramaDebounce?.cancel();
    _aramaController.dispose();
    _kelimeController.dispose();
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _fetchAllData() async {
    setState(() => _isLoading = true);
    await _fetchMevzuatlar();
    await _fetchOneriler();
    await _fetchKelimeler();
    if (mounted) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _fetchMevzuatlar() async {
    try {
      final res = await http.get(
        Uri.parse('$baseUrl/api/mevzuat/liste'),
        headers: {
          "Accept": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      );
      if (res.statusCode == 200) {
        final data = json.decode(utf8.decode(res.bodyBytes));
        if (mounted) {
          setState(() {
            _mevzuatlar = data['data'] ?? [];
          });
        }
      } else {
        _showSnackBar('Sunucu Hatası (${res.statusCode}): Veriler çekilemedi.');
      }
    } catch (e) {
      _showSnackBar('Bağlantı Kurulamadı: Backend servisinin çalıştığından emin olun.');
    }
  }

  Future<void> _fetchOneriler() async {
    try {
      final res = await http.get(
        Uri.parse('$baseUrl/api/oneriler'),
        headers: {
          "Accept": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      );
      if (res.statusCode == 200) {
        if (mounted) {
          setState(() {
            _oneriler = json.decode(utf8.decode(res.bodyBytes)) ?? [];
          });
        }
      }
    } catch (_) {}
  }

  Future<void> _fetchKelimeler() async {
    try {
      final res = await http.get(
        Uri.parse('$baseUrl/api/ayarlar/kelimeler'),
        headers: {
          "Accept": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      );
      if (res.statusCode == 200) {
        if (mounted) {
          setState(() {
            _kelimeler = json.decode(utf8.decode(res.bodyBytes)) ?? [];
          });
        }
      }
    } catch (_) {}
  }

  // YENİ: Arama fonksiyonu (debounce ile)
  void _aramaTetikle(String q) {
    _aramaDebounce?.cancel();
    if (q.trim().length < 2) {
      setState(() {
        _aramaSonuclari = [];
        _sonAramaTerimi = '';
      });
      return;
    }
    _aramaDebounce = Timer(const Duration(milliseconds: 400), () {
      _aramaYap(q.trim());
    });
  }

  Future<void> _aramaYap(String q) async {
    if (!mounted) return;
    setState(() {
      _aramaYapiliyor = true;
      _sonAramaTerimi = q;
    });

    try {
      final res = await http.get(
        Uri.parse('$baseUrl/api/arama?q=${Uri.encodeComponent(q)}'),
        headers: {"Accept": "application/json"},
      );

      if (res.statusCode == 200) {
        final data = json.decode(utf8.decode(res.bodyBytes));
        if (mounted) {
          setState(() {
            _aramaSonuclari = data['results'] ?? [];
            _aramaYapiliyor = false;
          });
        }
      } else {
        if (mounted) {
          setState(() => _aramaYapiliyor = false);
          _showSnackBar('Arama hatası: ${res.statusCode}');
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _aramaYapiliyor = false);
        _showSnackBar('Arama bağlantı hatası: $e');
      }
    }
  }

  Future<void> _triggerRevisionCheck() async {
    try {
      final res = await http.post(
        Uri.parse('$baseUrl/api/revizyon/tara'),
        headers: {"Accept": "application/json"},
      );
      if (res.statusCode == 200) {
        _showSnackBar('Resmî Gazete taranıyor...');
        await Future.delayed(const Duration(seconds: 4));
        _fetchAllData();
      }
    } catch (e) {
      _showSnackBar('Tarama yapılamadı: $e');
    }
  }

  Future<void> _addKelime(StateSetter setModalState) async {
    final text = _kelimeController.text.trim();
    if (text.isEmpty) return;

    try {
      final res = await http.post(
        Uri.parse('$baseUrl/api/ayarlar/kelime-ekle'),
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: json.encode({'kelime': text}),
      );

      if (res.statusCode == 200) {
        _kelimeController.clear();
        await _fetchKelimeler();
        setModalState(() {});
        _showSnackBar("'$text' takip kelimelerine eklendi.");
      }
    } catch (e) {
      _showSnackBar('Kelime ekleme hatası: $e');
    }
  }

  Future<void> _deleteKelime(int id, StateSetter setModalState) async {
    try {
      final res = await http.delete(
        Uri.parse('$baseUrl/api/ayarlar/kelime-sil/$id'),
        headers: {'Accept': 'application/json'},
      );
      if (res.statusCode == 200) {
        await _fetchKelimeler();
        setModalState(() {});
        _showSnackBar('Takip kelimesi silindi.');
      }
    } catch (e) {
      _showSnackBar('Silme hatası: $e');
    }
  }

  Future<void> _deleteMevzuat(int id, String baslik) async {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Mevzuatı Sil'),
        content: Text("'$baslik' kütüphaneden silinecek. Emin misiniz?"),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('İptal'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red, foregroundColor: Colors.white),
            onPressed: () async {
              try {
                final res = await http.delete(Uri.parse('$baseUrl/api/mevzuat/$id'));
                if (res.statusCode == 200) {
                  if (!mounted) return;
                  Navigator.pop(context);
                  _showSnackBar('Mevzuat başarıyla silindi.');
                  _fetchMevzuatlar();
                }
              } catch (_) {}
            },
            child: const Text('Sil'),
          ),
        ],
      ),
    );
  }

  Future<void> _acceptOneri(int id) async {
    try {
      final res = await http.post(Uri.parse('$baseUrl/api/oneriler/$id/kutuphaneye-ekle'));
      if (res.statusCode == 200) {
        _showSnackBar('Mevzuat kütüphanenize eklendi!');
        _fetchAllData();
      }
    } catch (_) {}
  }

  void _showSettingsDialog() {
    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return AlertDialog(
              title: const Row(
                children: [
                  Icon(Icons.settings, color: Color(0xFF1E3A8A)),
                  SizedBox(width: 8),
                  Text('Takip Kelimeleri Ayarları'),
                ],
              ),
              content: SizedBox(
                width: 450,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Resmî Gazete taranırken bu kelimelerin geçtiği mevzuatlar öneriler sekmesine düşer.',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _kelimeController,
                            decoration: const InputDecoration(
                              hintText: 'Ör. Vergi, İhale, Mal Alımı',
                              border: OutlineInputBorder(),
                              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF1E3A8A),
                            foregroundColor: Colors.white,
                          ),
                          icon: const Icon(Icons.add),
                          label: const Text('Ekle'),
                          onPressed: () => _addKelime(setModalState),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    const Text('Mevcut Kelimeler:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 8),
                    _kelimeler.isEmpty
                        ? const Text('Henüz eklenmiş bir takip kelimesi yok.', style: TextStyle(color: Colors.grey, fontSize: 13))
                        : Wrap(
                            spacing: 8,
                            runSpacing: 4,
                            children: _kelimeler.map((k) {
                              return Chip(
                                backgroundColor: Colors.blue.shade50,
                                label: Text(k['kelime'], style: const TextStyle(fontWeight: FontWeight.w600)),
                                deleteIcon: const Icon(Icons.cancel, size: 18, color: Colors.red),
                                onDeleted: () => _deleteKelime(k['id'], setModalState),
                              );
                            }).toList(),
                          ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Kapat'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showMevzuatFormDialog({Map<String, dynamic>? item}) {
    final bool isEdit = item != null;
    final urlController = TextEditingController(text: isEdit ? item['mevzuat_url'] : '');
    final noController = TextEditingController(text: isEdit ? item['mevzuat_no'] : '');
    final titleController = TextEditingController(text: isEdit ? item['baslik'] : '');
    String selectedTur = isEdit ? (item['tur'] ?? 'Kanun') : 'Kanun';

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(isEdit ? 'Mevzuat Bilgilerini Düzenle' : 'Kütüphaneye Yeni Mevzuat Ekle'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: urlController,
                      decoration: const InputDecoration(
                        labelText: 'mevzuat.gov.tr Bağlantısı (URL)',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: titleController,
                      decoration: const InputDecoration(
                        labelText: 'Mevzuat Başlığı / Adı',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: noController,
                            decoration: const InputDecoration(
                              labelText: 'Mevzuat No',
                              border: OutlineInputBorder(),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            value: ['Kanun', 'CBK', 'Yönetmelik', 'Tebliğ', 'KHK'].contains(selectedTur)
                                ? selectedTur
                                : 'Kanun',
                            decoration: const InputDecoration(
                              labelText: 'Mevzuat Türü',
                              border: OutlineInputBorder(),
                            ),
                            items: ['Kanun', 'CBK', 'Yönetmelik', 'Tebliğ', 'KHK']
                                .map((tur) => DropdownMenuItem(value: tur, child: Text(tur)))
                                .toList(),
                            onChanged: (val) {
                              if (val != null) setDialogState(() => selectedTur = val);
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(context), child: const Text('İptal')),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1E3A8A), foregroundColor: Colors.white),
                  onPressed: () async {
                    if (titleController.text.isEmpty) return;
                    http.Response response;
                    if (isEdit) {
                      response = await http.put(
                        Uri.parse('$baseUrl/api/mevzuat/${item['id']}'),
                        headers: {'Content-Type': 'application/json'},
                        body: json.encode({
                          'mevzuat_url': urlController.text.trim(),
                          'mevzuat_no': noController.text.trim(),
                          'baslik': titleController.text.trim(),
                          'tur': selectedTur,
                        }),
                      );
                    } else {
                      response = await http.post(
                        Uri.parse('$baseUrl/api/mevzuat/ekle'),
                        headers: {'Content-Type': 'application/json'},
                        body: json.encode({
                          'mevzuat_url': urlController.text.trim(),
                          'mevzuat_no': noController.text.trim(),
                          'baslik': titleController.text.trim(),
                          'tur': selectedTur,
                        }),
                      );
                    }
                    if (response.statusCode == 200) {
                      if (!mounted) return;
                      Navigator.pop(context);
                      _fetchAllData();
                    }
                  },
                  child: Text(isEdit ? 'Güncelle' : 'Kaydet'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _showMevzuatDetailDialog(int mevzuatId) async {
    showDialog(
      context: context,
      builder: (context) {
        return FutureBuilder<http.Response>(
          future: http.get(
            Uri.parse('$baseUrl/api/mevzuat/$mevzuatId'),
            headers: {"Accept": "application/json"},
          ),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const AlertDialog(
                content: SizedBox(height: 100, child: Center(child: CircularProgressIndicator())),
              );
            }

            if (!snapshot.hasData || snapshot.data!.statusCode != 200) {
              return const AlertDialog(content: Text('Mevzuat detayları çekilemedi.'));
            }

            final detail = json.decode(utf8.decode(snapshot.data!.bodyBytes));
            final List revizyonlar = detail['revizyonlar'] ?? [];
            final String icerikHtml = detail['icerik_html'] ?? '<p>Mevzuat metni henüz yüklenmedi.</p>';

            return DefaultTabController(
              length: 2,
              child: AlertDialog(
                title: Row(
                  children: [
                    const Icon(Icons.description, color: Color(0xFF1E3A8A)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        detail['baslik'] ?? '',
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                content: SizedBox(
                  width: 800,
                  height: 550,
                  child: Column(
                    children: [
                      const TabBar(
                        labelColor: Color(0xFF1E3A8A),
                        indicatorColor: Color(0xFF1E3A8A),
                        tabs: [
                          Tab(icon: Icon(Icons.article), text: 'Güncel Mevzuat Metni'),
                          Tab(icon: Icon(Icons.history), text: 'Revizyon Geçmişi ve Değişiklikler (Diff)'),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Expanded(
                        child: TabBarView(
                          children: [
                            SingleChildScrollView(
                              padding: const EdgeInsets.all(8),
                              child: HtmlWidget(icerikHtml),
                            ),
                            revizyonlar.isEmpty
                                ? const Center(child: Text('Bu mevzuat için kaydedilmiş değişiklik yok.'))
                                : ListView.builder(
                                    itemCount: revizyonlar.length,
                                    itemBuilder: (context, idx) {
                                      final rev = revizyonlar[idx];
                                      return Card(
                                        color: Colors.amber.shade50,
                                        margin: const EdgeInsets.only(bottom: 8),
                                        child: ListTile(
                                          title: Text(rev['baslik'] ?? '', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                                          subtitle: Text('${rev['tarih']} Resmî Gazete'),
                                          trailing: ElevatedButton.icon(
                                            style: ElevatedButton.styleFrom(
                                              backgroundColor: const Color(0xFF1E3A8A),
                                              foregroundColor: Colors.white,
                                            ),
                                            icon: const Icon(Icons.compare_arrows, size: 16),
                                            label: const Text('Yeşil/Kırmızı Farkı Gör'),
                                            onPressed: () => _showDiffDialog(rev['id']),
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Kapat'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _showDiffDialog(int revizyonId) async {
    showDialog(
      context: context,
      builder: (context) {
        return FutureBuilder<http.Response>(
          future: http.get(
            Uri.parse('$baseUrl/api/revizyon/$revizyonId/diff'),
            headers: {"Accept": "application/json"},
          ),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const AlertDialog(
                content: SizedBox(
                  height: 100,
                  child: Center(child: CircularProgressIndicator()),
                ),
              );
            }

            if (!snapshot.hasData || snapshot.data!.statusCode != 200) {
              return const AlertDialog(content: Text('Fark verisi çekilemedi.'));
            }

            final diffData = json.decode(utf8.decode(snapshot.data!.bodyBytes));
            final String diffHtml = diffData['diff_html'] ?? '<p>Fark bulunamadı.</p>';

            return AlertDialog(
              title: const Text('Değişiklik ve Metin Farkı (Diff)'),
              content: SizedBox(
                width: 750,
                height: 520,
                child: SingleChildScrollView(
                  child: HtmlWidget(diffHtml),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Kapat'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showSnackBar(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mevzuat Takip & Kütüphane'),
        backgroundColor: const Color(0xFF1E3A8A),
        foregroundColor: Colors.white,
        actions: [
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: const Color(0xFF1E3A8A),
            ),
            icon: const Icon(Icons.add, size: 18),
            label: const Text('Mevzuat Ekle', style: TextStyle(fontWeight: FontWeight.bold)),
            onPressed: () => _showMevzuatFormDialog(),
          ),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.sync),
            tooltip: 'Resmî Gazete Taraması Yap',
            onPressed: _triggerRevisionCheck,
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Takip Kelimeleri Ayarları',
            onPressed: _showSettingsDialog,
          ),
          const SizedBox(width: 8),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.amber,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: [
            Tab(icon: const Icon(Icons.library_books), text: 'Kütüphanem (${_mevzuatlar.length})'),
            Tab(
              icon: const Icon(Icons.auto_awesome),
              text: 'Mevzuat Önerileri (${_oneriler.length})',
            ),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildLibraryTab(),
                _buildSuggestionsTab(),
              ],
            ),
    );
  }

  // --- KÜTÜPHANE LİSTE TAB'I (ARAMA ÇUBUĞU İLE) ---
  Widget _buildLibraryTab() {
    return Column(
      children: [
        // YENİ: Arama çubuğu
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _aramaController,
            onChanged: _aramaTetikle,
            decoration: InputDecoration(
              hintText: 'Kütüphanede ara... (en az 2 karakter)',
              prefixIcon: const Icon(Icons.search, color: Color(0xFF1E3A8A)),
              suffixIcon: _aramaController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _aramaController.clear();
                        setState(() {
                          _aramaSonuclari = [];
                          _sonAramaTerimi = '';
                        });
                      },
                    )
                  : null,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              filled: true,
              fillColor: Colors.grey.shade50,
            ),
          ),
        ),
        // Arama yapılıyorsa sonuçları göster, yoksa normal listeyi
        Expanded(
          child: _aramaYapiliyor
              ? const Center(child: CircularProgressIndicator())
              : _sonAramaTerimi.isNotEmpty
                  ? _buildAramaSonuclari()
                  : _buildMevzuatListesi(),
        ),
      ],
    );
  }

  // YENİ: Arama sonuçlarını göster
  Widget _buildAramaSonuclari() {
    if (_aramaSonuclari.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 64, color: Colors.grey.shade400),
            const SizedBox(height: 16),
            Text(
              '"$_sonAramaTerimi" için sonuç bulunamadı.',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Farklı bir anahtar kelime deneyin.',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      itemCount: _aramaSonuclari.length,
      itemBuilder: (context, index) {
        final item = _aramaSonuclari[index];
        final int mevzuatId = item['id'];
        final bool baslikEslesme = item['baslik_eslesme'] ?? false;
        final String snippet = item['snippet'] ?? '';

        return Card(
          elevation: 2,
          margin: const EdgeInsets.only(bottom: 10),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => _showMevzuatDetailDialog(mevzuatId),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (baslikEslesme)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.green.shade100,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Başlıkta eşleşme',
                            style: TextStyle(fontSize: 10, color: Colors.green.shade900, fontWeight: FontWeight.bold),
                          ),
                        ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          item['tur'] ?? 'Mevzuat',
                          style: TextStyle(fontSize: 10, color: Colors.blue.shade900, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    item['baslik'] ?? '',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  if (snippet.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      snippet,
                      style: TextStyle(fontSize: 12, color: Colors.grey.shade700, fontStyle: FontStyle.italic),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  // YENİ: Normal mevzuat listesi (eski _buildLibraryTab içeriği)
  Widget _buildMevzuatListesi() {
    if (_mevzuatlar.isEmpty) {
      return const Center(child: Text('Kütüphanede henüz mevzuat yok.'));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _mevzuatlar.length,
      itemBuilder: (context, index) {
        final item = _mevzuatlar[index];
        final revCount = item['revizyon_sayisi'] ?? 0;
        final int mevzuatId = item['id'];

        return Card(
          elevation: 2,
          margin: const EdgeInsets.only(bottom: 10),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => _showMevzuatDetailDialog(mevzuatId),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
              child: Row(
                children: [
                  CircleAvatar(
                    backgroundColor: const Color(0xFF1E3A8A).withOpacity(0.1),
                    child: Text(
                      item['tur'] != null && item['tur'].toString().isNotEmpty
                          ? item['tur'][0]
                          : 'M',
                      style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF1E3A8A)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item['baslik'] ?? '',
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Mevzuat No: ${item['mevzuat_no']} | Son Güncelleme: ${item['son_guncelleme']}',
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                        ),
                      ],
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (revCount > 0)
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ActionChip(
                            avatar: const Icon(Icons.history, size: 16, color: Colors.amber),
                            label: Text('$revCount Yeni Revizyon'),
                            backgroundColor: Colors.amber.shade100,
                            onPressed: () => _showMevzuatDetailDialog(mevzuatId),
                          ),
                        ),
                      IconButton(
                        icon: const Icon(Icons.edit, color: Colors.blue),
                        tooltip: 'Düzenle',
                        onPressed: () => _showMevzuatFormDialog(item: item),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete, color: Colors.red),
                        tooltip: 'Sil',
                        onPressed: () => _deleteMevzuat(mevzuatId, item['baslik']),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildSuggestionsTab() {
    if (_oneriler.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.auto_awesome, size: 64, color: Colors.amber.shade300),
            const SizedBox(height: 16),
            const Text(
              'Henüz yeni bir mevzuat önerisi yok.',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Sağ üstteki Ayarlar simgesinden takip kelimelerinizi kontrol edebilirsiniz.',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _oneriler.length,
      itemBuilder: (context, index) {
        final sug = _oneriler[index];
        return Card(
          color: Colors.amber.shade50,
          elevation: 2,
          margin: const EdgeInsets.only(bottom: 10),
          child: ListTile(
            title: Text(sug['baslik'], style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('Eşleşen Takip Kelimesi: "${sug['eslesen_kelime']}"'),
            trailing: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1E3A8A),
                foregroundColor: Colors.white,
              ),
              icon: const Icon(Icons.playlist_add),
              label: const Text('Kütüphaneye Ekle'),
              onPressed: () => _acceptOneri(sug['id']),
            ),
          ),
        );
      },
    );
  }
}