import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count >= 5, let delay = Double(args[2]), delay > 0 else {
    fatalError("Usage: swift replay.swift OUTPUT.gif SECONDS FRAME1.png FRAME2.png ...")
}
let frames = Array(args.dropFirst(3))
let output = URL(fileURLWithPath: args[1])
guard !FileManager.default.fileExists(atPath: output.path),
      let gif = CGImageDestinationCreateWithURL(output as CFURL, UTType.gif.identifier as CFString,
                                                 frames.count, nil) else {
    fatalError("Cannot create GIF")
}
CGImageDestinationSetProperties(gif, [kCGImagePropertyGIFDictionary:
    [kCGImagePropertyGIFLoopCount: 0]] as CFDictionary)
for (index, path) in frames.enumerated() {
    guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        fatalError("Cannot decode frame: \(path)")
    }
    let duration = index == frames.count - 1 ? max(1.8, delay) : delay
    CGImageDestinationAddImage(gif, image, [kCGImagePropertyGIFDictionary:
        [kCGImagePropertyGIFDelayTime: duration, kCGImagePropertyGIFUnclampedDelayTime: duration]] as CFDictionary)
}
guard CGImageDestinationFinalize(gif) else { fatalError("Could not write GIF") }
