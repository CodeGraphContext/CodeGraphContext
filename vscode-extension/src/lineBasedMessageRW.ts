/* --------------------------------------------------------------------------------------------
 * Copyright (c) Microsoft Corporation. All rights reserved.
 * Licensed under the MIT License. See License.txt in the project root for license information.
 * ------------------------------------------------------------------------------------------ */
import { MessageReader, MessageWriter, AbstractMessageReader, AbstractMessageWriter, Disposable, DataCallback, Message } from 'vscode-jsonrpc';
import { Readable, Writable } from 'stream';

export class LineMessageReader extends AbstractMessageReader implements MessageReader {

    private readable: Readable;
    private callback: DataCallback | undefined;
    private buffer: Buffer = Buffer.alloc(0);

    constructor(readable: Readable, encoding: BufferEncoding = 'utf8') {
        super();
        this.readable = readable;
        this.readable.on('data', (data: Buffer) => this.onData(data));
        this.readable.on('error', (error: any) => this.fireError(error));
        this.readable.on('close', () => this.fireClose());
    }

    private onData(data: Buffer): void {
        this.buffer = Buffer.concat([this.buffer, data]);
        while (true) {
            const index = this.buffer.indexOf('\n');
            if (index === -1) {
                break;
            }
            const content = this.buffer.slice(0, index).toString('utf8');
            this.buffer = this.buffer.slice(index + 1);
            if (content.trim().length === 0) {
                continue;
            }
            try {
                const message = JSON.parse(content);
                this.callback!(message);
            } catch (error) {
                this.fireError(error);
            }
        }
    }

    public listen(callback: DataCallback): Disposable {
        this.callback = callback;
        return {
            dispose: () => {
                this.callback = undefined;
            }
        };
    }
}

export class LineMessageWriter extends AbstractMessageWriter implements MessageWriter {

    private writable: Writable;

    constructor(writable: Writable, encoding: BufferEncoding = 'utf8') {
        super();
        this.writable = writable;
        this.writable.on('error', (error: any) => this.fireError(error));
        this.writable.on('close', () => this.fireClose());
    }

    public async write(msg: Message): Promise<void> {
        const content = JSON.stringify(msg);
        this.writable.write(content + '\n', 'utf8');
    }

    public end(): void {
        this.writable.end();
    }
}
