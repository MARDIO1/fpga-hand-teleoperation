# Build directly on the PYNQ Linux target.
CXX ?= g++
CXXFLAGS := -std=c++11 -O2 -Wall -Wextra

hand_server: hand_server.cpp hand_accel.cpp hand_accel.hpp ../../hls/hand_core.hpp ../protocol/hand_udp_protocol.hpp
	$(CXX) $(CXXFLAGS) hand_server.cpp hand_accel.cpp -o $@

clean:
	rm -f hand_server
