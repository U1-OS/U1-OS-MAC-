import AppKit

let size = 1024
let space = CGColorSpaceCreateDeviceRGB()
let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: size * 4, space: space, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
ctx.scaleBy(x: 8, y: 8)
ctx.translateBy(x: 0, y: 128)
ctx.scaleBy(x: 1, y: -1)
ctx.setFillColor(CGColor(red: 0.031, green: 0.090, blue: 0.173, alpha: 1))
ctx.addPath(CGPath(roundedRect: CGRect(x: 5, y: 5, width: 118, height: 118), cornerWidth: 28, cornerHeight: 28, transform: nil))
ctx.fillPath()
ctx.setStrokeColor(CGColor(red: 0.34, green: 0.61, blue: 0.81, alpha: 0.65))
ctx.addPath(CGPath(roundedRect: CGRect(x: 5, y: 5, width: 118, height: 118), cornerWidth: 28, cornerHeight: 28, transform: nil))
ctx.setLineWidth(0.6); ctx.strokePath()
ctx.translateBy(x: 10, y: 8); ctx.scaleBy(x: 0.84, y: 0.84)
let u = CGMutablePath()
u.move(to: CGPoint(x: 18, y: 27)); u.addLine(to: CGPoint(x: 37, y: 27)); u.addLine(to: CGPoint(x: 37, y: 78))
u.addCurve(to: CGPoint(x: 52, y: 95), control1: CGPoint(x: 37, y: 89), control2: CGPoint(x: 42, y: 95))
u.addCurve(to: CGPoint(x: 67, y: 78), control1: CGPoint(x: 62, y: 95), control2: CGPoint(x: 67, y: 89))
u.addLine(to: CGPoint(x: 67, y: 48)); u.addLine(to: CGPoint(x: 86, y: 34)); u.addLine(to: CGPoint(x: 86, y: 79))
u.addCurve(to: CGPoint(x: 52, y: 115), control1: CGPoint(x: 86, y: 102), control2: CGPoint(x: 73, y: 115))
u.addCurve(to: CGPoint(x: 18, y: 79), control1: CGPoint(x: 31, y: 115), control2: CGPoint(x: 18, y: 102)); u.closeSubpath()
ctx.saveGState(); ctx.addPath(u); ctx.clip()
let colors = [CGColor(red: 0.69, green: 1, blue: 1, alpha: 1), CGColor(red: 0.26, green: 0.89, blue: 1, alpha: 1), CGColor(red: 0.14, green: 0.44, blue: 1, alpha: 1)] as CFArray
let gradient = CGGradient(colorsSpace: space, colors: colors, locations: [0, 0.42, 1])!
ctx.drawLinearGradient(gradient, start: CGPoint(x: 24, y: 20), end: CGPoint(x: 88, y: 114), options: [.drawsBeforeStartLocation, .drawsAfterEndLocation]); ctx.restoreGState()
let one = CGMutablePath()
one.addLines(between: [CGPoint(x:66,y:37),CGPoint(x:92,y:17),CGPoint(x:109,y:17),CGPoint(x:109,y:115),CGPoint(x:90,y:115),CGPoint(x:90,y:44),CGPoint(x:66,y:62)])
one.closeSubpath(); ctx.addPath(one)
ctx.setFillColor(CGColor(red: 0.86, green: 0.94, blue: 1, alpha: 1)); ctx.fillPath()
let image = ctx.makeImage()!
let bitmap = NSBitmapImageRep(cgImage: image)
try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
