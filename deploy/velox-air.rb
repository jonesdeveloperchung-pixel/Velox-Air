class VeloxAir < Formula
  desc "Passive web-based secondary display server"
  homepage "https://github.com/jonesdeveloperchung-pixel/Velox-Air"
  url "https://github.com/jonesdeveloperchung-pixel/Velox-Air/releases/download/v1.0.0/VeloxAir_Server_macOS.zip"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  version "1.0.0"

  def install
    bin.install "VeloxAir_Server" => "velox-air"
  end

  test do
    system "#{bin}/velox-air", "--version"
  end
end
