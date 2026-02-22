"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ImageGalleryProps {
  title: string;
  subtitle: string;
  images: string[];
  getImageUrl: (filename: string) => string;
}

export function ImageGallery({
  title,
  subtitle,
  images,
  getImageUrl,
}: ImageGalleryProps) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  if (images.length === 0) return null;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {images.map((filename) => (
              <button
                key={filename}
                onClick={() => setSelectedImage(filename)}
                className="relative aspect-square overflow-hidden rounded-lg border hover:ring-2 hover:ring-primary transition-all"
              >
                <img
                  src={getImageUrl(filename)}
                  alt={filename}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs px-2 py-1 truncate">
                  {filename}
                </span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Full-size image modal */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={getImageUrl(selectedImage)}
              alt={selectedImage}
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
            />
            <button
              onClick={() => setSelectedImage(null)}
              className="absolute -top-3 -right-3 bg-white text-black rounded-full w-8 h-8 flex items-center justify-center shadow-lg hover:bg-gray-100"
            >
              X
            </button>
            <p className="text-white text-center mt-2 text-sm">
              {selectedImage}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
