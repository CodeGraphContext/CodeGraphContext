import { ClassA } from './tough_cases';

export class ClassB {
    constructor(private a?: ClassA) {}
    
    respond() {
        console.log("ClassB responding");
        if (this.a) {
            this.a.ping();
        }
    }
}
