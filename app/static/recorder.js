class BoundedRecorder extends AudioWorkletProcessor {
  process(inputs, outputs) {
    for (const output of outputs) for (const channel of output) channel.fill(0);
    const channel = inputs[0]?.[0];
    if (channel) this.port.postMessage(channel.slice());
    return true;
  }
}
registerProcessor('bounded-recorder', BoundedRecorder);
