import Foundation
import ImageIO
import Vision

struct Label: Encodable {
    let text: String
    let confidence: Float
    let x: Int
    let y: Int
    let width: Int
    let height: Int
}

let args = CommandLine.arguments
guard args.count >= 2 else { fatalError("Usage: swift read_reference.swift REFERENCE [en-US zh-Hans]") }
let url = URL(fileURLWithPath: args[1])
guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
      let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [String: Any],
      let rawWidth = properties[kCGImagePropertyPixelWidth as String] as? Int,
      let rawHeight = properties[kCGImagePropertyPixelHeight as String] as? Int else {
    fatalError("Could not read reference image")
}
let orientation = properties[kCGImagePropertyOrientation as String] as? Int ?? 1
let rotated = (5...8).contains(orientation)
let width = rotated ? rawHeight : rawWidth
let height = rotated ? rawWidth : rawHeight
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
if args.count > 2 { request.recognitionLanguages = Array(args.dropFirst(2)) }
do {
    try VNImageRequestHandler(url: url, options: [:]).perform([request])
} catch {
    FileHandle.standardError.write(Data("macOS Vision OCR failed: \(error)\n".utf8))
    exit(1)
}
let labels: [Label] = (request.results ?? []).compactMap { observation in
    guard let hit = observation.topCandidates(1).first else { return nil }
    let box = observation.boundingBox
    return Label(text: hit.string, confidence: hit.confidence,
                 x: Int((box.minX * Double(width)).rounded()),
                 y: Int(((1 - box.maxY) * Double(height)).rounded()),
                 width: Int((box.width * Double(width)).rounded()),
                 height: Int((box.height * Double(height)).rounded()))
}
struct Reference: Encodable {
    let width: Int
    let height: Int
    let labels: [Label]
}
let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
let json = try encoder.encode(Reference(width: width, height: height, labels: labels))
FileHandle.standardOutput.write(json)
