import Foundation
import CoreLocation

// talks to PRISMO through oracle. everything clever happens on the pi, the app just asks and reports
enum API {
    static let base = "https://132-226-199-122.sslip.io"
    static let key = "uQdB49GyUzfskLgWUVrixhVBekwwgkkh"

    static func url(_ path: String, _ query: [String: String] = [:]) -> URL {
        var c = URLComponents(string: base + path)!
        c.queryItems = [URLQueryItem(name: "key", value: key)] + query.map { URLQueryItem(name: $0.key, value: $0.value) }
        return c.url!
    }

    static func get(_ path: String, _ query: [String: String] = [:], timeout: Double = 30) async throws -> Data {
        var r = URLRequest(url: url(path, query))
        r.timeoutInterval = timeout
        let (data, resp) = try await URLSession.shared.data(for: r)
        if let h = resp as? HTTPURLResponse, h.statusCode >= 400 {
            throw NSError(domain: "PRISMO", code: h.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: String(data: data, encoding: .utf8) ?? "Fehler \(h.statusCode)"])
        }
        return data
    }

    static func ask(_ mode: String, _ loc: CLLocation?) async -> String {
        var q = ["mode": mode]
        if let l = loc {
            q["lat"] = String(l.coordinate.latitude)
            q["lon"] = String(l.coordinate.longitude)
        }
        do {
            let d = try await get("/day/now", q)
            let t = String(data: d, encoding: .utf8) ?? ""
            return t.isEmpty ? "Nix los gerade 💤" : t
        } catch {
            return "PRISMO antwortet nicht 💤\n\(error.localizedDescription)"
        }
    }

    static func event(_ name: String) async {
        _ = try? await get("/day/event", ["e": name], timeout: 20)
    }

    struct Place: Decodable { let lat: Double; let lon: Double; let r: Double }
    static func places() async throws -> [String: Place] {
        try JSONDecoder().decode([String: Place].self, from: try await get("/day/places"))
    }

    struct Wake: Decodable { let date: String; let alarm: String; let why: String }
    static func alarms() async throws -> [Wake] {
        try JSONDecoder().decode([Wake].self, from: try await get("/day/alarms", [:], timeout: 40))
    }
}
