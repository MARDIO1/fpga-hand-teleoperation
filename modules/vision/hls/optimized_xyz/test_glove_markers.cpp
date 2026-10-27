#include "glove_markers.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using Expected = std::array<unsigned, 8>;

static void require(bool valid, const std::string& reason) {
    if (!valid) throw std::runtime_error(reason);
}

static unsigned word(const Packet& packet, int index) {
    return packet.data.range(index * 32 + 31, index * 32).to_uint();
}

static void check_case(const std::string& stem) {
    std::ifstream fixture(stem + ".txt");
    unsigned width, height, expected_errors, bad_protocol, min_area, max_area;
    require(bool(fixture >> width >> height >> expected_errors >> bad_protocol >> min_area >> max_area), "Missing fixture: " + stem);
    ColorThreshold thresholds[4];
    for (int i = 0; i < 4; ++i) {
        unsigned hmin, hmax, smin, vmin;
        fixture >> hmin >> hmax >> smin >> vmin;
        thresholds[i] = {hmin, hmax, smin, vmin};
    }
    unsigned expected_count;
    fixture >> expected_count;
    std::vector<Expected> expected(expected_count);
    for (auto& row : expected) for (auto& value : row) fixture >> value;
    require(bool(fixture), "Truncated fixture " + stem);
    std::ifstream raw(stem + ".rgb565", std::ios::binary);
    hls::stream<Pixel> pixels;
    hls::stream<Packet> output;
    for (unsigned y = 0; y < height; ++y) for (unsigned x = 0; x < width; ++x) {
        unsigned char bytes[2];
        raw.read(reinterpret_cast<char*>(bytes), 2);
        require(bool(raw), "Truncated RGB565 " + stem);
        Pixel pixel;
        pixel.data = unsigned(bytes[0]) | unsigned(bytes[1]) << 8;
        pixel.keep = pixel.strb = 3;
        pixel.user = x == 0 && y == 0;
        pixel.last = x + 1 == width;
        if (bad_protocol && x == 0 && y == 0) pixel.user = 0;
        pixel.id = pixel.dest = 0;
        pixels.write(pixel);
    }
    const ap_uint<32> frame_id = 73;
    const ap_uint<64> timestamp = 0x123456789abcULL;
    glove_markers(pixels, output, thresholds, width, height, min_area, max_area, frame_id, timestamp);
    require(pixels.empty(), "Input not drained " + stem);
    std::vector<Expected> actual;
    bool summary_seen = false;
    while (!output.empty()) {
        Packet packet = output.read();
        require(packet.keep == ap_uint<40>(-1) && packet.strb == ap_uint<40>(-1), "Bad output byte mask");
        require(word(packet, 6) == frame_id.to_uint(), "Frame ID changed");
        require(packet.data.range(287, 224) == timestamp, "Timestamp changed");
        require(!summary_seen, "Output after frame summary");
        if (packet.last) {
            summary_seen = true;
            require(word(packet, 0) == (1u | expected_errors << 16), "Wrong frame status " + stem);
            require(word(packet, 9) == actual.size() && actual.size() == expected_count, "Wrong region count " + stem);
            require(packet.user == 1, "Summary USER missing");
        } else {
            require(packet.user == 0 && (word(packet, 0) & 0xffff00ff) == 0, "Wrong region packet header");
            Expected row = {{(word(packet, 0) >> 8) & 255, word(packet, 1), word(packet, 2), word(packet, 3),
                             word(packet, 4) & 65535, word(packet, 4) >> 16,
                             word(packet, 5) & 65535, word(packet, 5) >> 16}};
            actual.push_back(row);
        }
    }
    require(summary_seen, "No frame summary " + stem);
    std::sort(actual.begin(), actual.end());
    std::sort(expected.begin(), expected.end());
    require(actual == expected, "Component statistics differ " + stem);
    std::cout << "PASS " << stem << " regions=" << actual.size() << std::endl;
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: test_glove_markers manifest.txt");
        std::string manifest = argv[1];
        std::string directory = manifest.substr(0, manifest.find_last_of("/\\") + 1);
        std::ifstream list(manifest);
        require(bool(list), "Missing manifest " + manifest);
        std::string stem;
        unsigned cases = 0;
        while (std::getline(list, stem)) if (!stem.empty()) {
            check_case(stem);
            ++cases;
        }
        // Exhaustive independent Python color oracle. Kept out of synthesis.
        for (int eye = 0; eye < 2; ++eye) {
            ColorThreshold thresholds[4] = {{165,10,100,55},{22,42,90,100},{43,85,80,55},{100,134,110,55}};
            if (eye == 1) {
                thresholds[0].h_min = 155;
                thresholds[1].s_min = 35;
                thresholds[2].s_min = 55;
                thresholds[3].s_min = 140;
                thresholds[3].v_min = 100;
            }
            std::ifstream oracle(directory + (eye ? "colors_R.bin" : "colors_L.bin"), std::ios::binary);
            require(bool(oracle), "Missing exhaustive color oracle");
            for (unsigned value = 0; value < 65536; ++value) {
                char expected;
                require(bool(oracle.get(expected)), "Truncated color oracle");
                require(classify_pixel(value, thresholds) == static_cast<unsigned char>(expected), "RGB565 classification differs");
            }
        }
        // Configuration failure emits a summary and does not consume a frame.
        hls::stream<Pixel> input;
        hls::stream<Packet> output;
        ColorThreshold thresholds[4] = {};
        glove_markers(input, output, thresholds, 0, 720, 1, 100, 9, 10);
        require(!output.empty() && word(output.read(), 0) == (1 | BAD_CONFIG << 16), "Invalid config not reported");
        require(output.empty(), "Invalid config emitted extra packets");
        std::cout << "PASS " << cases << " frames, both 65536-color oracles, invalid config" << std::endl;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << std::endl;
        return 1;
    }
}
