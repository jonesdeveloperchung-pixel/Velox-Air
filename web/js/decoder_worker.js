// decoder_worker.js - Parallel WebP Decoder (Velox Air Version)

self.onmessage = async (e) => {
    const { id, tileData, x, y, width, height, isFull } = e.data;
    
    try {
        const blob = new Blob([tileData], { type: 'image/webp' });
        
        if (typeof self.createImageBitmap === 'function') {
            const bitmap = await self.createImageBitmap(blob);
            self.postMessage({
                id,
                bitmap,
                x, y, width, height, isFull
            }, [bitmap]);
        } else {
            // Fallback for VERY old browsers: Send back the blob
            self.postMessage({
                id,
                blob,
                x, y, width, height, isFull
            });
        }
    } catch (err) {
        self.postMessage({ id, error: err.message });
    }
};
